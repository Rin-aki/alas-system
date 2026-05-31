<template>
  <div class="verify-container">
    <div class="glass-panel super-glass animate-entry">
      <div class="header">
        <h2>ALAS</h2>
        <p class="subtitle">邮箱验证</p>
      </div>

      <div v-if="state === 'loading'" class="status-block">
        <el-icon class="spin icon-large"><Loading /></el-icon>
        <p>正在验证，请稍候…</p>
      </div>

      <div v-else-if="state === 'success'" class="status-block">
        <el-icon class="icon-large success"><CircleCheck /></el-icon>
        <p class="status-msg">邮箱验证成功，账户已激活！</p>
        <el-button type="primary" round class="action-btn" @click="goLogin">
          前往登录
        </el-button>
      </div>

      <div v-else class="status-block">
        <el-icon class="icon-large error"><CircleClose /></el-icon>
        <p class="status-msg">{{ errorMsg }}</p>
        <div class="resend-area">
          <el-input
            v-model="email"
            placeholder="输入注册邮箱重新发送"
            :prefix-icon="Message"
            size="large"
          />
          <el-button
            type="primary"
            round
            class="action-btn"
            :loading="resending"
            @click="resend"
          >
            重新发送验证邮件
          </el-button>
          <el-button round class="action-btn" @click="goLogin">返回登录</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, CircleClose, Loading, Message } from '@element-plus/icons-vue'
import { userService } from '../../services/api.js'

const route = useRoute()
const router = useRouter()

const state = ref('loading') // loading | success | error
const errorMsg = ref('')
const email = ref('')
const resending = ref(false)

onMounted(async () => {
  const token = route.query.token
  if (!token) {
    state.value = 'error'
    errorMsg.value = '验证链接无效，缺少 token 参数。'
    return
  }
  try {
    const res = await userService.verifyEmail(token)
    if (res.ok) {
      state.value = 'success'
    } else {
      state.value = 'error'
      errorMsg.value = res.data?.detail || res.data?.error || '验证失败，链接可能已过期。'
    }
  } catch {
    state.value = 'error'
    errorMsg.value = '网络错误，请稍后重试。'
  }
})

const resend = async () => {
  if (!email.value) {
    ElMessage.warning('请输入注册时使用的邮箱')
    return
  }
  resending.value = true
  try {
    const res = await userService.resendVerification(email.value)
    if (res.ok) {
      ElMessage.success(res.data?.msg || '验证邮件已发送，请查收')
    } else {
      ElMessage.error(res.data?.detail || res.data?.error || '发送失败，请稍后重试')
    }
  } catch {
    ElMessage.error('网络错误，请稍后重试')
  } finally {
    resending.value = false
  }
}

const goLogin = () => router.push('/login')
</script>

<style scoped>
.verify-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
}

.glass-panel {
  width: 100%;
  max-width: 420px;
  padding: 40px 35px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h2 {
  font-size: 2.8em;
  margin: 0;
  background: linear-gradient(120deg, #a1c4fd 0%, #c2e9fb 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 4px;
  font-weight: 800;
}

.subtitle {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 0.95em;
}

.status-block {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.icon-large {
  font-size: 56px;
}

.icon-large.success {
  color: #67c23a;
}

.icon-large.error {
  color: #f56c6c;
}

.spin {
  color: #409eff;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.status-msg {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
}

.resend-area {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;
}

.action-btn {
  width: 100%;
  font-size: 15px;
  padding: 20px 0;
}
</style>
