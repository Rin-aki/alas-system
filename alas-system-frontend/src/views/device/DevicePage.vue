<template>
  <div class="device-fullscreen" ref="containerRef">
    <!-- 状态遮罩 -->
    <div v-if="state !== 'streaming'" class="overlay">
      <div class="status-card">
        <template v-if="state === 'loading'">
          <div class="spinner"></div>
          <p class="status-text">{{ statusText }}</p>
        </template>
        <template v-else>
          <p class="error-text">{{ errorText }}</p>
          <button class="btn-back" @click="goBack">返回控制台</button>
        </template>
      </div>
    </div>

    <!-- 视频画布 -->
    <canvas
      ref="canvasRef"
      class="video-canvas"
      @pointerdown.prevent="onPointerDown"
      @pointerup.prevent="onPointerUp"
      @pointermove.prevent="onPointerMove"
      @pointercancel.prevent="onPointerUp"
      @contextmenu.prevent
    />

    <!-- 断开按钮 -->
    <div v-if="state === 'streaming'" class="hud">
      <button class="btn-disconnect" @click="disconnect">断开连接</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { resolveRuntimeUrl } from '../../services/api.js'

const router = useRouter()

// ── URL 推导 ────────────────────────────────────────────────────
const _proxyBase = resolveRuntimeUrl(
  import.meta.env.VITE_SCRCPY_BASE_URL || 'http://localhost:6300/'
).replace(/\/$/, '')
const HTTP_BASE = _proxyBase
const WS_BASE   = _proxyBase.replace(/^https/, 'wss').replace(/^http/, 'ws')

const DEVICE_START_URL = `${HTTP_BASE}/api/device/start`
const DEVICE_STOP_URL  = `${HTTP_BASE}/api/device/stop`
const DEVICE_WS_URL    = `${WS_BASE}/api/device/ws`

// ── 响应式状态 ───────────────────────────────────────────────────
const state      = ref('loading')
const statusText = ref('正在启动设备...')
const errorText  = ref('')

const canvasRef    = ref(null)
const containerRef = ref(null)

// ── 运行时变量 ──────────────────────────────────────────────────
let ws             = null
let decoder        = null
let deviceW        = 0
let deviceH        = 0
let activePointers = new Set()

// scrcpy 协议状态
let initialParsed = false

// WebCodecs 缓冲区 (仿照 ws-scrcpy WebCodecsPlayer)
let naluBuffer  = null   // Uint8Array
let hadIDR      = false
let bufferedSPS = false
let bufferedPPS = false

// ── 生命周期 ─────────────────────────────────────────────────────
onMounted(async () => {
  try {
    statusText.value = '正在启动设备...'
    await startDevice()
    statusText.value = '正在连接流媒体...'
    openWebSocket()
  } catch (e) {
    showError(e.message || '启动失败')
  }
})

onBeforeUnmount(() => cleanUp())

// ── 启动设备（HTTP） ─────────────────────────────────────────────
async function startDevice() {
  const res = await fetch(DEVICE_START_URL, { method: 'POST', credentials: 'include' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
}

// ── WebSocket ────────────────────────────────────────────────────
function openWebSocket() {
  ws = new WebSocket(DEVICE_WS_URL)
  ws.binaryType = 'arraybuffer'

  ws.onmessage = (evt) => {
    if (evt.data instanceof ArrayBuffer) {
      handleBinary(new Uint8Array(evt.data))
    }
    // text 消息忽略（透明代理不会发文本）
  }

  ws.onerror = () => showError('WebSocket 连接失败')

  ws.onclose = (evt) => {
    if (state.value === 'streaming') {
      showError(`连接已断开 (${evt.code})`)
    }
  }
}

// ── scrcpy_initial 解析 ──────────────────────────────────────────
const MAGIC = 'scrcpy_initial'

function checkMagic(data) {
  if (data.length < MAGIC.length) return false
  for (let i = 0; i < MAGIC.length; i++) {
    if (data[i] !== MAGIC.charCodeAt(i)) return false
  }
  return true
}

function parseInitial(data) {
  // 布局: [14B magic][64B device name][4B displays_count]
  //        per display: [24B DisplayInfo][4B connCount][4B siLen][siLen B ScreenInfo][4B vsLen][vsLen B VideoSettings]
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength)
  let offset = MAGIC.length + 64  // 跳过 magic + device name

  if (offset + 4 > data.length) return fallback()
  const displaysCount = view.getInt32(offset, false)
  offset += 4

  if (displaysCount <= 0) return fallback()

  // DisplayInfo: displayId(4)+width(4)+height(4)+rotation(4)+layerStack(4)+flags(4) = 24 bytes
  if (offset + 24 > data.length) return fallback()
  const dispW = view.getInt32(offset + 4, false)
  const dispH = view.getInt32(offset + 8, false)
  offset += 24

  // connectionCount
  if (offset + 4 > data.length) return { width: dispW || 720, height: dispH || 1280 }
  offset += 4

  // screenInfo
  if (offset + 4 > data.length) return { width: dispW || 720, height: dispH || 1280 }
  const siLen = view.getInt32(offset, false)
  offset += 4

  let w = dispW, h = dispH
  if (siLen >= 25 && offset + siLen <= data.length) {
    // ScreenInfo: left(4)+top(4)+right(4)+bottom(4)+videoWidth(4)+videoHeight(4)+rotation(1)
    const siW = view.getInt32(offset + 16, false)
    const siH = view.getInt32(offset + 20, false)
    if (siW > 0 && siH > 0) { w = siW; h = siH }
  }

  return { width: w || 720, height: h || 1280 }
}

function fallback() { return { width: 720, height: 1280 } }

// ── 二进制消息处理 ───────────────────────────────────────────────
function handleBinary(data) {
  // scrcpy 可能在设置生效后发送第二个 scrcpy_initial（含更新后的 ScreenInfo）
  if (checkMagic(data)) {
    const info = parseInitial(data)
    deviceW = info.width
    deviceH = info.height
    setupCanvas(deviceW, deviceH)
    if (!initialParsed) {
      state.value = 'streaming'
      initialParsed = true
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(makeVideoSettings())
      }
    }
    return
  }
  if (!initialParsed) return
  processNalu(data)
}

// ── Canvas ───────────────────────────────────────────────────────
function setupCanvas(w, h) {
  const c = canvasRef.value
  c.width  = w
  c.height = h
  applyCanvasScale()
}

function applyCanvasScale() {
  const c = canvasRef.value
  if (!c || !c.width) return
  const scale = Math.min(window.innerWidth / c.width, window.innerHeight / c.height)
  const left  = (window.innerWidth  - c.width  * scale) / 2
  const top   = (window.innerHeight - c.height * scale) / 2
  c.style.transform       = `scale(${scale})`
  c.style.transformOrigin = '0 0'
  c.style.left            = `${left}px`
  c.style.top             = `${top}px`
}

window.addEventListener('resize', applyCanvasScale)
onBeforeUnmount(() => window.removeEventListener('resize', applyCanvasScale))

// ── TYPE_CHANGE_STREAM_PARAMETERS (101) ─────────────────────────
// 格式与 ws-scrcpy CommandControlMessage.createSetVideoSettingsCommand 完全一致
function makeVideoSettings() {
  const buf  = new ArrayBuffer(36)  // 1 type + 35 VideoSettings (BASE_BUFFER_LENGTH)
  const view = new DataView(buf)
  let pos = 0
  view.setUint8 (pos, 101);             pos += 1  // TYPE_CHANGE_STREAM_PARAMETERS
  view.setInt32 (pos, 8_000_000, false);pos += 4  // bitrate
  view.setInt32 (pos, 60,        false);pos += 4  // maxFps
  view.setInt8  (pos, 10);              pos += 1  // iFrameInterval
  view.setInt16 (pos, 720,       false);pos += 2  // bounds width
  view.setInt16 (pos, 720,       false);pos += 2  // bounds height
  view.setInt16 (pos, 0,         false);pos += 2  // crop left
  view.setInt16 (pos, 0,         false);pos += 2  // crop top
  view.setInt16 (pos, 0,         false);pos += 2  // crop right
  view.setInt16 (pos, 0,         false);pos += 2  // crop bottom
  view.setInt8  (pos, 0);               pos += 1  // sendFrameMeta = false
  view.setInt8  (pos, -1);              pos += 1  // lockedVideoOrientation = auto
  view.setInt32 (pos, 0,         false);pos += 4  // displayId
  view.setInt32 (pos, 0,         false);pos += 4  // codecOptions length
  view.setInt32 (pos, 0,         false)            // encoderName length
  return buf
}

// ── H264 NAL 处理 (仿 ws-scrcpy WebCodecsPlayer.decode) ─────────
// scrcpy 以 Annex B 格式发送: [00 00 00 01][NAL header][NAL data...]
// data[4] & 0x1f = NAL unit type
//   7 = SPS, 8 = PPS, 5 = IDR, 1 = P-frame
function concatU8(a, b) {
  const out = new Uint8Array(a.length + b.length)
  out.set(a, 0)
  out.set(b, a.length)
  return out
}

function addToNaluBuffer(data) {
  naluBuffer = naluBuffer ? concatU8(naluBuffer, data) : new Uint8Array(data)
  return naluBuffer
}

function processNalu(data) {
  if (data.length < 5) return
  const nalType = data[4] & 0x1f

  if (nalType === 7) {  // SPS
    const codec = spsToCodec(data)
    if (codec) initDecoder(codec)
    bufferedSPS = true
    addToNaluBuffer(data)
    hadIDR = false  // 新 SPS 意味着新序列，重置 IDR 标志
    return
  }

  if (nalType === 8) {  // PPS
    bufferedPPS = true
    addToNaluBuffer(data)
    return
  }

  // SEI / IDR / P-frame: 追加到缓冲区
  const combined = addToNaluBuffer(data)
  const isIDR    = (nalType === 5)
  hadIDR         = hadIDR || isIDR

  // 必须已配置解码器且见过第一个 IDR 才开始解码
  if (decoder && decoder.state === 'configured' && hadIDR) {
    const bufCopy = combined.buffer.slice(
      combined.byteOffset,
      combined.byteOffset + combined.byteLength
    )
    naluBuffer  = null
    bufferedSPS = false
    bufferedPPS = false
    try {
      decoder.decode(new EncodedVideoChunk({
        type: 'key',
        timestamp: performance.now() * 1000,
        data: bufCopy,
      }))
    } catch (e) {
      console.error('[WebCodecs]', e)
    }
  }
}

// SPS (data[4]=0x67) 中提取 avc1.PPCCLL
function spsToCodec(data) {
  // data = [00 00 00 01][0x67][profile][constraints][level]...
  if (data.length < 8) return null
  const p = data[5].toString(16).padStart(2, '0')
  const c = data[6].toString(16).padStart(2, '0')
  const l = data[7].toString(16).padStart(2, '0')
  return `avc1.${p}${c}${l}`
}

function initDecoder(codec) {
  if (typeof VideoDecoder === 'undefined') {
    showError('浏览器不支持 WebCodecs API，请使用 Chrome 94+')
    return
  }
  if (decoder && decoder.state !== 'closed') decoder.close()
  const ctx = canvasRef.value.getContext('2d')
  decoder = new VideoDecoder({
    output(frame) {
      ctx.drawImage(frame, 0, 0, canvasRef.value.width, canvasRef.value.height)
      frame.close()
    },
    error(e) { console.error('[VideoDecoder]', e) },
  })
  decoder.configure({
    codec,
    hardwareAcceleration: 'prefer-hardware',
    optimizeForLatency: true,
  })
}

// ── 触控事件 ──────────────────────────────────────────────────────
function toDeviceCoords(clientX, clientY) {
  const rect = canvasRef.value.getBoundingClientRect()
  const x = Math.round((clientX - rect.left) * (deviceW / rect.width))
  const y = Math.round((clientY - rect.top)  * (deviceH / rect.height))
  return {
    x: Math.max(0, Math.min(deviceW - 1, x)),
    y: Math.max(0, Math.min(deviceH - 1, y)),
  }
}

function sendTouch(action, pointerId, clientX, clientY, pressure, buttons) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  const { x, y } = toDeviceCoords(clientX, clientY)
  const buf  = new ArrayBuffer(29)  // TYPE_TOUCH (1) + payload (28)
  const view = new DataView(buf)
  view.setUint8 (0,  2)                               // TYPE_TOUCH
  view.setUint8 (1,  action)
  view.setUint32(2,  0,                        false) // pointerId high 32 bits
  view.setUint32(6,  pointerId & 0xFFFFFFFF,   false)
  view.setUint32(10, x,                        false)
  view.setUint32(14, y,                        false)
  view.setUint16(18, deviceW,                  false)
  view.setUint16(20, deviceH,                  false)
  view.setUint16(22, Math.round(pressure * 0xFFFF), false)
  view.setUint32(24, buttons,                  false)
  ws.send(buf)
}

function onPointerDown(evt) {
  canvasRef.value.setPointerCapture(evt.pointerId)
  activePointers.add(evt.pointerId)
  sendTouch(0, evt.pointerId, evt.clientX, evt.clientY, evt.pressure || 1, evt.buttons)
}

function onPointerMove(evt) {
  if (!activePointers.has(evt.pointerId)) return
  sendTouch(2, evt.pointerId, evt.clientX, evt.clientY, evt.pressure || 1, evt.buttons)
}

function onPointerUp(evt) {
  activePointers.delete(evt.pointerId)
  sendTouch(1, evt.pointerId, evt.clientX, evt.clientY, 0, 0)
}

// ── 断开 & 清理 ───────────────────────────────────────────────────
function disconnect() {
  cleanUp()
  fetch(DEVICE_STOP_URL, { method: 'POST', credentials: 'include' }).catch(() => {})
  router.push('/dashboard')
}

function cleanUp() {
  if (ws) { ws.onclose = null; ws.close(); ws = null }
  if (decoder && decoder.state !== 'closed') { decoder.close(); decoder = null }
  naluBuffer    = null
  hadIDR        = false
  bufferedSPS   = false
  bufferedPPS   = false
  initialParsed = false
  activePointers.clear()
}

function showError(msg) {
  errorText.value = msg
  state.value = 'error'
}

function goBack() {
  cleanUp()
  router.push('/dashboard')
}
</script>

<style scoped>
.device-fullscreen {
  position: fixed;
  inset: 0;
  background: #000;
  overflow: hidden;
  touch-action: none;
  user-select: none;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.85);
  z-index: 10;
}

.status-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px 40px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  backdrop-filter: blur(12px);
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.2);
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-text {
  color: rgba(255, 255, 255, 0.85);
  font-size: 15px;
  margin: 0;
}

.error-text {
  color: #f56c6c;
  font-size: 15px;
  margin: 0;
  text-align: center;
  max-width: 280px;
}

.btn-back {
  padding: 8px 24px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}
.btn-back:hover { background: #66b1ff; }

.video-canvas {
  position: absolute;
  display: block;
  cursor: crosshair;
}

.hud {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 20;
}

.btn-disconnect {
  padding: 8px 20px;
  background: rgba(245, 108, 108, 0.85);
  color: #fff;
  border: none;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: background 0.2s;
}
.btn-disconnect:hover { background: rgba(245, 108, 108, 1); }
</style>
