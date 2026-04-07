<template>
  <div class="fix-container">
    <div class="glass-panel super-glass animate-entry">
      <div class="header-bar">
        <div class="status-indicator">
          <div class="dot" :class="connectionStatus"></div>
          <span class="status-text">{{ statusText }}</span>
        </div>
        <div class="warning-tag" v-if="connectionStatus === 'active'">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>修复进行中，请保持页面开启</span>
        </div>
      </div>

      <div class="terminal-window" ref="terminalRef">
        <div class="terminal-header">
          <div class="window-dot red"></div>
          <div class="window-dot yellow"></div>
          <div class="window-dot green"></div>
          <span class="window-title">root@alas-repair:~</span>
        </div>
        
        <div class="terminal-body">
          <div v-for="(line, index) in logs" :key="index" class="log-line">
            <span class="prompt">➜</span>
            <span class="content">{{ line }}</span>
          </div>
          <div class="cursor-line" v-if="connectionStatus !== 'closed'">
            <span class="prompt">➜</span>
            <span class="cursor">_</span>
          </div>
        </div>
      </div>
    
      <div class="footer-tip">
        <p v-if="connectionStatus === 'closed'">
          连接已断开，正在跳转回主页...
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Loading } from '@element-plus/icons-vue'
import { resolveRuntimeUrl } from '../../services/api.js'

const router = useRouter()
const logs = ref([])
const terminalRef = ref(null)
const ws = ref(null)
const connectionStatus = ref('pending') // pending, active, closed, error

// 计算状态文字
const statusText = computed(() => {
  switch (connectionStatus.value) {
    case 'pending': return '正在建立连接...'
    case 'active': return '正在执行修复脚本...'
    case 'closed': return '修复结束'
    case 'error': return '连接发生错误'
    default: return '未知状态'
  }
})

// 滚动到底部函数
const scrollToBottom = async () => {
  await nextTick()
  if (terminalRef.value) {
    const body = terminalRef.value.querySelector('.terminal-body')
    if (body) {
      body.scrollTop = body.scrollHeight
    }
  }
}

const appendLog = (msg) => {
  // 简单的清洗，去掉可能多余的换行符
  const cleanMsg = msg.trim()
  if (cleanMsg) {
    logs.value.push(cleanMsg)
    scrollToBottom()
  }
}

onMounted(() => {
  // 初始化 WebSocket
  const wsUrl = resolveRuntimeUrl(import.meta.env.VITE_WS_FIX_URL || 'ws://localhost:6200/fix')
  
  try {
    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      connectionStatus.value = 'active'
      appendLog('System connected. Starting diagnosis...')
    }

    ws.value.onmessage = (event) => {
      appendLog(event.data)
    }

    ws.value.onerror = (err) => {
      connectionStatus.value = 'error'
      appendLog('Error: WebSocket connection failed.')
      console.error(err)
    }

    ws.value.onclose = () => {
      connectionStatus.value = 'closed'
      appendLog('Connection closed. Redirecting in 3 seconds...')
      // 3秒后跳转
      setTimeout(() => {
        router.replace('/dashboard')
      }, 3000)
    }
  } catch (e) {
    connectionStatus.value = 'error'
    appendLog('Fatal Error: Failed to initialize connection.')
  }
})

onUnmounted(() => {
  if (ws.value) {
    ws.value.close()
  }
})
</script>

<style scoped>
.fix-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
}

.glass-panel {
  width: 100%;
  max-width: 800px; /* 比登录页宽一些 */
  height: 80vh;
  padding: 20px;
  display: flex;
  flex-direction: column;
}

/* 顶部栏 */
.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding: 0 10px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #909399;
  transition: all 0.3s;
}

.dot.active {
  background-color: #67c23a;
  box-shadow: 0 0 8px #67c23a;
  animation: pulse 2s infinite;
}

.dot.error { background-color: #f56c6c; }
.dot.closed { background-color: #e6a23c; }

.status-text {
  font-weight: bold;
  color: var(--text-main);
}

.warning-tag {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #e6a23c;
  background: rgba(230, 162, 60, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
}

/* 终端窗口核心样式 */
.terminal-window {
  flex: 1;
  background-color: #1e1e1e;
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.1);
}

.terminal-header {
  background-color: #2d2d2d;
  padding: 8px 15px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #333;
}

.window-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.window-dot.red { background-color: #ff5f56; }
.window-dot.yellow { background-color: #ffbd2e; }
.window-dot.green { background-color: #27c93f; }

.window-title {
  margin-left: 10px;
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 12px;
  color: #999;
}

.terminal-body {
  flex: 1;
  padding: 15px;
  overflow-y: auto;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.6;
  color: #f0f0f0;
}

/* 滚动条样式自定义 */
.terminal-body::-webkit-scrollbar {
  width: 8px;
}
.terminal-body::-webkit-scrollbar-track {
  background: #1e1e1e;
}
.terminal-body::-webkit-scrollbar-thumb {
  background: #444;
  border-radius: 4px;
}

.log-line {
  word-break: break-all;
  margin-bottom: 4px;
  display: flex;
}

.prompt {
  color: #27c93f; /* 终端绿 */
  margin-right: 10px;
  user-select: none;
  font-weight: bold;
}

.content {
  color: #d4d4d4;
}

/* 简单的光标动画 */
.cursor {
  color: #27c93f;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

.footer-tip {
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 0.9em;
  margin-top: 10px;
}
</style>
