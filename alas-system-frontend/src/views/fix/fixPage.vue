<template>
  <div>
    <h2>修复中...</h2>
    <el-input
      v-model="log"
      type="textarea"
      :rows="15"
      readonly
      style="width: 100%"
    />
  </div>
</template>

<script>
export default {
  data() {
    return {
      log: '',
      ws: null,
    }
  },
  methods: {
    appendLog(msg) {
      this.log += msg + '\n'
    }
  },
  mounted() {
    const wsUrl = import.meta.env.VITE_WS_FIX_URL || 'wss://api.gjiang.xyz:58000/fix'
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      this.appendLog('WebSocket连接成功，开始修复...')
    }

    this.ws.onmessage = (event) => {
      this.appendLog(event.data)
    }

    this.ws.onerror = (err) => {
      this.appendLog('WebSocket出错')
      console.error(err)
    }

    this.ws.onclose = () => {
      this.appendLog('连接已关闭，3秒后返回控制台...')
      setTimeout(() => {
        this.$router.push('/')
      }, 3000)
    }
  },
  beforeUnmount() {
    if (this.ws) {
      this.ws.close()
    }
  }
}
</script>
