<template>
  <div class="dashboard-container animate-entry">
    <div class="header-section">
      <h2>控制台</h2>
      <p class="welcome-text">欢迎回来，指挥官</p>
    </div>

    <!-- 系统公告横幅 -->
    <el-alert
      v-if="announcement"
      :title="announcement.title"
      :description="announcement.content"
      type="info"
      :closable="true"
      show-icon
      style="margin-bottom: 20px;"
    />

    <!-- 维护模式提示 -->
    <el-alert
      v-if="systemStatus.is_maintenance"
      title="系统维护中"
      :description="systemStatus.maintenance_message"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 20px;"
    />

    <el-row :gutter="20">
      <el-col :xs="24" :md="10" :lg="8">
        <div class="glass-card super-glass profile-card">
          <div class="avatar-section">
            <el-avatar :size="80" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png" />
            <h3>{{ user.email || 'Loading...' }}</h3>
            <p class="uid">UID: {{ user.id }}</p>
          </div>
          
          <div class="info-list">
            <div class="info-item">
              <span>购买状态</span>
              <el-tag :type="purchaseStatus.has_purchased ? 'success' : 'info'" effect="dark" round>
                {{ purchaseStatus.has_purchased ? '已激活' : '未激活' }}
              </el-tag>
            </div>
            <div class="info-item" v-if="purchaseStatus.has_purchased">
              <span>剩余天数</span>
              <span class="highlight-value">{{ purchaseStatus.days_remaining }} 天</span>
            </div>
            <div class="info-item" v-if="purchaseStatus.has_purchased">
              <span>过期时间</span>
              <span class="date-text">{{ formatDate(purchaseStatus.purchase_expires) }}</span>
            </div>
          </div>
          
          <div class="logout-btn-wrapper">
            <el-button type="danger" plain round style="width: 100%" @click="logout" :icon="SwitchButton">
              退出登录
            </el-button>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :md="14" :lg="16">
        <div class="glass-card super-glass action-card">
          <h3 class="card-title">实例控制</h3>
          
          <div class="action-grid">
            <div class="action-item" @click="linkblhx">
              <div class="icon-box blue">
                <el-icon><Monitor /></el-icon>
              </div>
              <span>连接实例</span>
              <p>远程游戏控制</p>
            </div>

            <div class="action-item" @click="linkalas">
              <div class="icon-box green">
                <el-icon><Setting /></el-icon>
              </div>
              <span>连接 ALAS</span>
              <p>配置脚本参数</p>
            </div>

            <div class="action-item" @click="reconnect">
              <div class="icon-box orange" :class="{ 'spinning': reconnecting }">
                <el-icon><Refresh /></el-icon>
              </div>
              <span>{{ reconnecting ? '重连中...' : '重连服务' }}</span>
              <p>连接实例页面失效时使用</p>
            </div>

            <div class="action-item" @click="fix">
              <div class="icon-box red">
                <el-icon><FirstAidKit /></el-icon>
              </div>
              <span>重启服务</span>
              <p>解决游戏卡死/alas异常</p>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Monitor, Setting, Refresh, FirstAidKit, SwitchButton } from '@element-plus/icons-vue'
import { resolveRuntimeUrl, userService } from '../../services/api.js'

const router = useRouter()
const loading = ref(false)
const reconnecting = ref(false)

const user = reactive({
  email: "",
  id: null
})

const purchaseStatus = reactive({
  has_purchased: false,
  purchase_expires: null,
  days_remaining: 0
})

const announcement = ref(null)
const systemStatus = reactive({
  is_maintenance: false,
  maintenance_message: ''
})

const SCRCPY_BASE_URL = resolveRuntimeUrl(import.meta.env.VITE_SCRCPY_BASE_URL || 'http://localhost:6300/', { service: 'scrcpy' })
const ALAS_BASE_URL = resolveRuntimeUrl(import.meta.env.VITE_ALAS_BASE_URL || 'http://localhost:6300/', { service: 'alas' })

// 初始化逻辑 (保持原有逻辑不变，转为 Composition API 写法)
const initUser = async () => {
  try {
    const res = await userService.getUserInfo()
    if (!res.ok) {
      router.replace('/login')
      return
    }

    user.email = res.data.email ?? ''
    user.id = res.data.user_id ?? null
    localStorage.setItem('email', user.email)
    localStorage.setItem('user_id', user.id ?? '')
    localStorage.setItem('ip', res.data.alas_ip ?? '')
  } catch {
    router.replace('/login')
  }
}

const getPurchaseStatus = async () => {
  loading.value = true
  try {
    const res = await userService.getPurchaseStatus()
    if (res.status === 200) {
      Object.assign(purchaseStatus, res.data)
    } else if (res.status === 422) {
      logout()
    }
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '无'
  return new Date(dateStr).toLocaleDateString()
}

// 获取公告
const getAnnouncement = async () => {
  try {
    const res = await userService.getLatestAnnouncement()
    if (res.ok && res.data) {
      announcement.value = res.data
    }
  } catch (err) {
    console.error('获取公告失败:', err)
  }
}

// 获取系统状态
const getSystemStatus = async () => {
  try {
    const res = await userService.getSystemStatus()
    if (res.ok && res.data) {
      Object.assign(systemStatus, res.data)
    }
  } catch (err) {
    console.error('获取系统状态失败:', err)
  }
}

// 动作函数
const checkAuth = () => {
  if (!purchaseStatus.has_purchased) {
    ElMessage.warning('您尚未购买服务')
    return false
  }
  // 检查维护状态
  if (systemStatus.is_maintenance) {
    ElMessage.warning(systemStatus.maintenance_message || '系统维护中，请稍后再试')
    return false
  }
  return true
}

const linkblhx = () => {
  if (!checkAuth()) return
  router.push('/device')
}

const linkalas = () => {
  if (!checkAuth()) return
  window.location.href = ALAS_BASE_URL
}

const fix = () => {
  if (!checkAuth()) return
  router.push('/fix')
}

const reconnect = async () => {
  if (!checkAuth()) return
  reconnecting.value = true
  try {
    const res = await userService.reconnect()
    if (res.status === 200 && res.data.success) {
      ElMessage.success('服务重启成功')
    } else {
      ElMessage.error('重启失败')
    }
  } catch {
    ElMessage.error('网络错误')
  } finally {
    reconnecting.value = false
  }
}

const logout = async () => {
  localStorage.clear()
  try {
    await userService.logout()
  } catch (e) { console.log(e) }
  router.replace('/login')
}

onMounted(() => {
  initUser()
  getPurchaseStatus()
  getAnnouncement()
  getSystemStatus()
})
</script>

<style scoped>
.dashboard-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 20px;
}

.header-section {
  margin-bottom: 30px;
  text-align: left;
  color: white;
}

.header-section h2 {
  margin: 0;
  font-size: 2.5em;
  text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.welcome-text {
  opacity: 0.8;
  margin-top: 5px;
}

.glass-card {
  padding: 30px;
  margin-bottom: 20px;
  height: 100%;
}

/* 左侧个人信息卡 */
.avatar-section {
  text-align: center;
  margin-bottom: 30px;
}

.avatar-section h3 {
  margin: 15px 0 5px;
  font-size: 1.2em;
}

.uid {
  color: var(--text-secondary);
  font-size: 0.9em;
}

.info-list {
  margin-bottom: 30px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.highlight-value {
  color: #67c23a;
  font-weight: bold;
}

/* 右侧动作卡 */
.card-title {
  margin-top: 0;
  margin-bottom: 25px;
  border-left: 4px solid var(--primary-color);
  padding-left: 10px;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.action-item {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 25px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.action-item:hover {
  background: rgba(255, 255, 255, 0.15);
  transform: translateY(-5px);
}

.icon-box {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  margin-bottom: 15px;
}

.icon-box.blue { background: rgba(64, 158, 255, 0.2); color: #409eff; }
.icon-box.green { background: rgba(103, 194, 58, 0.2); color: #67c23a; }
.icon-box.orange { background: rgba(230, 162, 60, 0.2); color: #e6a23c; }
.icon-box.red { background: rgba(245, 108, 108, 0.2); color: #f56c6c; }

.spinning {
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.action-item span {
  font-weight: bold;
  font-size: 1.1em;
  margin-bottom: 5px;
}

.action-item p {
  margin: 0;
  font-size: 0.85em;
  color: var(--text-secondary);
}
</style>
