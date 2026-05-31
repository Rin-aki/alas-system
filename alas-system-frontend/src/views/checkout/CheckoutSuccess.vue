<template>
  <div class="result-container animate-entry">
    <div class="glass-card super-glass result-card">
      <div v-if="loading" class="state-wrap">
        <el-icon class="is-loading" :size="48"><Loading /></el-icon>
        <p>验证支付结果中...</p>
      </div>

      <div v-else-if="paid" class="state-wrap success">
        <el-icon :size="64" color="#67c23a"><CircleCheckFilled /></el-icon>
        <h2>充值成功！</h2>
        <p>已为您激活 <strong>{{ days }}</strong> 天服务</p>
        <el-button type="primary" size="large" round @click="router.replace('/dashboard')">
          返回控制台
        </el-button>
      </div>

      <div v-else class="state-wrap pending">
        <el-icon :size="64" color="#e6a23c"><WarningFilled /></el-icon>
        <h2>支付处理中</h2>
        <p>订单正在确认，通常在几秒内完成。<br>若长时间未到账，请联系管理员。</p>
        <el-button type="primary" size="large" round @click="router.replace('/dashboard')">
          返回控制台
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Loading, CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'
import { userService } from '../../services/api.js'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const paid = ref(false)
const days = ref(0)

onMounted(async () => {
  const sessionId = route.query.session_id
  if (!sessionId) {
    router.replace('/dashboard')
    return
  }

  // Poll up to 5 times with 1s delay to wait for webhook delivery
  for (let i = 0; i < 5; i++) {
    try {
      const res = await userService.verifyPayment(sessionId)
      if (res.ok && res.data.paid) {
        paid.value = true
        days.value = res.data.days
        break
      }
    } catch {
      // ignore, retry
    }
    if (i < 4) await new Promise(r => setTimeout(r, 1200))
  }

  loading.value = false
})
</script>

<style scoped>
.result-container {
  max-width: 500px;
  margin: 80px auto;
  padding: 20px;
}

.result-card {
  padding: 50px 40px;
}

.state-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
  color: white;
}

.state-wrap h2 {
  margin: 0;
  font-size: 1.8em;
}

.state-wrap p {
  margin: 0;
  opacity: 0.85;
  line-height: 1.6;
}
</style>
