<template>
  <div class="checkout-container animate-entry">
    <div class="header-section">
      <h2>充值套餐</h2>
      <p class="welcome-text">选择适合您的套餐，立即开始使用</p>
    </div>

    <div v-if="loading" class="loading-wrap">
      <el-icon class="is-loading" :size="40"><Loading /></el-icon>
    </div>

    <div v-else>
      <el-row :gutter="20" justify="center">
        <el-col
          v-for="plan in plans"
          :key="plan.id"
          :xs="24" :sm="12" :md="6"
        >
          <div
            class="glass-card super-glass plan-card"
            :class="{ selected: selectedPlanId === plan.id }"
            @click="selectedPlanId = plan.id"
          >
            <div class="plan-label">{{ plan.label }}</div>
            <div class="plan-price">
              <span class="price-currency">¥</span>
              <span class="price-amount">{{ (plan.amount / 100).toFixed(0) }}</span>
            </div>
            <div class="plan-days">{{ plan.days }} 天</div>
            <div class="plan-unit">≈ ¥{{ (plan.amount / plan.days / 100).toFixed(2) }} / 天</div>
          </div>
        </el-col>
      </el-row>

      <div class="checkout-action">
        <el-button
          type="primary"
          size="large"
          round
          :disabled="!selectedPlanId"
          :loading="paying"
          @click="startPayment"
        >
          {{ paying ? '跳转支付中...' : '立即付款' }}
        </el-button>
        <el-button size="large" round @click="router.push('/dashboard')">返回控制台</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { userService } from '../../services/api.js'

const router = useRouter()
const loading = ref(true)
const paying = ref(false)
const plans = ref([])
const selectedPlanId = ref(null)

onMounted(async () => {
  try {
    const res = await userService.getPaymentPlans()
    if (res.ok) {
      plans.value = res.data
    } else {
      ElMessage.error('获取套餐信息失败，请刷新重试')
    }
  } catch {
    ElMessage.error('网络错误，请刷新重试')
  } finally {
    loading.value = false
  }
})

const startPayment = async () => {
  if (!selectedPlanId.value) return
  paying.value = true
  try {
    const res = await userService.createCheckoutSession(selectedPlanId.value)
    if (res.ok && res.data.url) {
      window.location.href = res.data.url
    } else {
      ElMessage.error(res.data?.detail || '创建支付会话失败，请稍后重试')
    }
  } catch {
    ElMessage.error('网络错误，请稍后重试')
  } finally {
    paying.value = false
  }
}
</script>

<style scoped>
.checkout-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px 20px;
}

.header-section {
  margin-bottom: 40px;
  text-align: center;
  color: white;
}

.header-section h2 {
  margin: 0;
  font-size: 2.5em;
  text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.welcome-text {
  opacity: 0.8;
  margin-top: 8px;
}

.loading-wrap {
  display: flex;
  justify-content: center;
  padding: 80px 0;
  color: white;
}

.plan-card {
  padding: 30px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s;
  margin-bottom: 20px;
  border: 2px solid transparent;
}

.plan-card:hover {
  transform: translateY(-6px);
  border-color: rgba(64, 158, 255, 0.5);
}

.plan-card.selected {
  border-color: #409eff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.25);
}

.plan-label {
  font-size: 1.1em;
  font-weight: bold;
  margin-bottom: 16px;
  color: var(--text-secondary, rgba(255,255,255,0.7));
}

.plan-price {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  margin-bottom: 8px;
}

.price-currency {
  font-size: 1.2em;
  margin-top: 6px;
  color: #409eff;
}

.price-amount {
  font-size: 3em;
  font-weight: bold;
  color: #409eff;
  line-height: 1;
}

.plan-days {
  font-size: 1.4em;
  font-weight: bold;
  margin-bottom: 6px;
}

.plan-unit {
  font-size: 0.85em;
  color: var(--text-secondary, rgba(255,255,255,0.5));
}

.checkout-action {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 40px;
}
</style>
