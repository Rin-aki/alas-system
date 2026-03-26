<template>
  <div class="admin-container animate-entry">
    <div class="header-section">
      <h2>管理员面板</h2>
      <p class="welcome-text">系统管理与配置</p>
    </div>

    <el-row :gutter="20">
      <!-- 发布公告 -->
      <el-col :xs="24" :lg="12">
        <div class="glass-card super-glass">
          <h3 class="card-title">发布系统公告</h3>
          <el-form :model="announcementForm" label-width="80px">
            <el-form-item label="标题">
              <el-input v-model="announcementForm.title" placeholder="请输入公告标题" />
            </el-form-item>
            <el-form-item label="内容">
              <el-input
                v-model="announcementForm.content"
                type="textarea"
                :rows="4"
                placeholder="请输入公告内容"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="publishAnnouncement" :loading="publishing">
                发布公告
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-col>

      <!-- 维护模式控制 -->
      <el-col :xs="24" :lg="12">
        <div class="glass-card super-glass">
          <h3 class="card-title">系统维护模式</h3>
          <el-form :model="maintenanceForm" label-width="100px">
            <el-form-item label="维护状态">
              <el-switch
                v-model="maintenanceForm.is_maintenance"
                active-text="维护中"
                inactive-text="正常运行"
                :active-value="true"
                :inactive-value="false"
              />
            </el-form-item>
            <el-form-item label="提示信息">
              <el-input
                v-model="maintenanceForm.maintenance_message"
                type="textarea"
                :rows="3"
                placeholder="维护期间显示的提示信息"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                :type="maintenanceForm.is_maintenance ? 'danger' : 'success'"
                @click="updateMaintenance"
                :loading="updating"
              >
                {{ maintenanceForm.is_maintenance ? '启用维护模式' : '关闭维护模式' }}
              </el-button>
            </el-form-item>
          </el-form>

          <el-alert
            v-if="maintenanceForm.is_maintenance"
            title="警告"
            description="启用维护模式后，所有用户将无法使用管理面板中的功能按钮"
            type="warning"
            :closable="false"
            show-icon
            style="margin-top: 20px;"
          />
        </div>
      </el-col>
    </el-row>

    <!-- 返回和登出按钮 -->
    <div style="margin-top: 20px; display: flex; gap: 10px;">
      <el-button @click="logout" type="danger">退出登录</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminService } from '../../services/api.js'

const router = useRouter()
const publishing = ref(false)
const updating = ref(false)

const announcementForm = reactive({
  title: '',
  content: ''
})

const maintenanceForm = reactive({
  is_maintenance: false,
  maintenance_message: '系统维护中，请稍后再试'
})

// 发布公告
const publishAnnouncement = async () => {
  if (!announcementForm.title || !announcementForm.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }

  publishing.value = true
  try {
    const res = await adminService.createAnnouncement({
      title: announcementForm.title,
      content: announcementForm.content
    })

    if (res.ok) {
      ElMessage.success('公告发布成功')
      announcementForm.title = ''
      announcementForm.content = ''
    } else {
      ElMessage.error('发布失败: ' + (res.data?.detail || '未知错误'))
    }
  } catch (err) {
    ElMessage.error('网络错误')
    console.error(err)
  } finally {
    publishing.value = false
  }
}

// 更新维护状态
const updateMaintenance = async () => {
  updating.value = true
  try {
    const res = await adminService.updateMaintenance({
      is_maintenance: maintenanceForm.is_maintenance,
      maintenance_message: maintenanceForm.maintenance_message
    })

    if (res.ok) {
      ElMessage.success('维护状态更新成功')
    } else {
      ElMessage.error('更新失败: ' + (res.data?.detail || '未知错误'))
    }
  } catch (err) {
    ElMessage.error('网络错误')
    console.error(err)
  } finally {
    updating.value = false
  }
}

// 获取当前维护状态
const loadCurrentStatus = async () => {
  try {
    const res = await adminService.getSystemStatus()
    if (res.ok && res.data) {
      Object.assign(maintenanceForm, res.data)
    }
  } catch (err) {
    console.error('获取系统状态失败:', err)
  }
}

// 管理员登出
const logout = async () => {
  try {
    await adminService.logout()
    ElMessage.success('已退出登录')
    router.push('/admin-login')
  } catch (err) {
    console.error('登出失败:', err)
    router.push('/admin-login')
  }
}

onMounted(() => {
  loadCurrentStatus()
})
</script>

<style scoped>
.admin-container {
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
}

.card-title {
  margin-top: 0;
  margin-bottom: 25px;
  border-left: 4px solid var(--primary-color);
  padding-left: 10px;
}
</style>
