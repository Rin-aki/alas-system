<template>
  <div class="admin-container animate-entry">
    <div class="header-section">
      <h2>管理员面板</h2>
      <p class="welcome-text">系统管理与配置</p>
    </div>

    <!-- 用户管理 -->
    <div class="glass-card super-glass" style="margin-bottom: 20px;">
      <h3 class="card-title">用户管理</h3>
      <el-table :data="users" v-loading="loadingUsers" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="email" label="邮箱" min-width="200" />
        <el-table-column label="激活" width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :loading="row._activating"
              @change="(val) => handleSetActive(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="已购买" width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.has_purchased"
              :loading="row._purchaseUpdating"
              @change="(val) => handleSetPurchased(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="到期时间" min-width="200">
          <template #default="{ row }">
            <el-date-picker
              v-model="row._editExpiry"
              type="datetime"
              format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DDTHH:mm:ss"
              placeholder="设置到期时间"
              size="small"
              style="width: 190px"
              :loading="row._expiryUpdating"
              @change="(val) => handleSetExpiry(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="快捷延期" min-width="260">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" :loading="row._extending" @click="extendUser(row, 1)">+1月</el-button>
              <el-button size="small" :loading="row._extending" @click="extendUser(row, 3)">+3月</el-button>
              <el-button size="small" :loading="row._extending" @click="extendUser(row, 6)">+半年</el-button>
              <el-button size="small" type="primary" :loading="row._extending" @click="extendUser(row, 12)">+1年</el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-row :gutter="20">
      <!-- 公告管理 -->
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

          <el-divider>已有公告</el-divider>
          <div v-if="!loadingAnnouncements && announcements.length === 0" style="text-align: center; opacity: 0.5; padding: 10px 0;">
            暂无公告
          </div>
          <el-table :data="announcements" v-loading="loadingAnnouncements" size="small" style="width: 100%">
            <el-table-column prop="title" label="标题" min-width="120" show-overflow-tooltip />
            <el-table-column label="时间" width="120">
              <template #default="{ row }">{{ formatDateShort(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="60">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '当前' : '历史' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="" width="60">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click="deleteAnnouncement(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
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

    <div style="margin-top: 20px; display: flex; gap: 10px;">
      <el-button @click="logout" type="danger">退出登录</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminService } from '../../services/api.js'

const router = useRouter()
const publishing = ref(false)
const updating = ref(false)
const loadingUsers = ref(false)
const loadingAnnouncements = ref(false)

const users = ref([])
const announcements = ref([])

const announcementForm = reactive({ title: '', content: '' })
const maintenanceForm = reactive({
  is_maintenance: false,
  maintenance_message: '系统维护中，请稍后再试'
})

const formatDate = (dateStr) => {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

const formatDateShort = (dateStr) => {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
    + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const loadUsers = async () => {
  loadingUsers.value = true
  try {
    const res = await adminService.listUsers()
    if (res.ok) {
      users.value = res.data.map(u => ({
        ...u,
        _extending: false,
        _activating: false,
        _purchaseUpdating: false,
        _expiryUpdating: false,
        _editExpiry: u.purchase_expires || null
      }))
    }
  } catch (err) {
    console.error('加载用户列表失败:', err)
  } finally {
    loadingUsers.value = false
  }
}

const loadAnnouncements = async () => {
  loadingAnnouncements.value = true
  try {
    const res = await adminService.listAnnouncements()
    if (res.ok) {
      announcements.value = res.data
    }
  } catch (err) {
    console.error('加载公告列表失败:', err)
  } finally {
    loadingAnnouncements.value = false
  }
}

const handleSetActive = async (row, newVal) => {
  row._activating = true
  try {
    const res = await adminService.setUserActive(row.id, newVal)
    if (res.ok) {
      row.is_active = newVal
      ElMessage.success(newVal ? '已激活用户' : '已禁用用户')
    } else {
      ElMessage.error('操作失败: ' + (res.data?.detail || res.data?.message || '未知错误'))
    }
  } catch (err) {
    ElMessage.error('网络错误')
    console.error(err)
  } finally {
    row._activating = false
  }
}

const extendUser = async (row, months) => {
  row._extending = true
  try {
    const res = await adminService.extendPurchase(row.id, months)
    if (res.ok) {
      row.purchase_expires = res.data.purchase_expires
      row._editExpiry = res.data.purchase_expires
      row.has_purchased = true
      ElMessage.success(`已延期 ${months} 个月，新到期时间：${formatDate(res.data.purchase_expires)}`)
    } else {
      ElMessage.error('延期失败: ' + (res.data?.detail || res.data?.message || '未知错误'))
    }
  } catch (err) {
    ElMessage.error('网络错误')
    console.error(err)
  } finally {
    row._extending = false
  }
}

const handleSetPurchased = async (row, newVal) => {
  row._purchaseUpdating = true
  try {
    const res = await adminService.setPurchaseStatus(row.id, newVal)
    if (res.ok) {
      row.has_purchased = res.data.has_purchased
      ElMessage.success(newVal ? '已开启购买状态' : '已关闭购买状态')
    } else {
      ElMessage.error('操作失败: ' + (res.data?.detail || res.data?.message || '未知错误'))
    }
  } catch (err) {
    ElMessage.error('网络错误')
    console.error(err)
  } finally {
    row._purchaseUpdating = false
  }
}

const handleSetExpiry = async (row, val) => {
  row._expiryUpdating = true
  try {
    const res = await adminService.setPurchaseStatus(row.id, true, val)
    if (res.ok) {
      row.purchase_expires = res.data.purchase_expires
      row._editExpiry = res.data.purchase_expires
      row.has_purchased = true
      ElMessage.success('到期时间已更新：' + formatDate(res.data.purchase_expires))
    } else {
      row._editExpiry = row.purchase_expires
      ElMessage.error('设置失败: ' + (res.data?.detail || res.data?.message || '未知错误'))
    }
  } catch (err) {
    row._editExpiry = row.purchase_expires
    ElMessage.error('网络错误')
    console.error(err)
  } finally {
    row._expiryUpdating = false
  }
}

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
      loadAnnouncements()
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

const deleteAnnouncement = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除公告「${row.title}」吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    const res = await adminService.deleteAnnouncement(row.id)
    if (res.ok) {
      ElMessage.success('公告已删除')
      announcements.value = announcements.value.filter(a => a.id !== row.id)
    } else {
      ElMessage.error('删除失败: ' + (res.data?.detail || '未知错误'))
    }
  } catch (err) {
    ElMessage.error('网络错误')
    console.error(err)
  }
}

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

const logout = async () => {
  try {
    await adminService.logout()
    ElMessage.success('已退出登录')
    router.push('/admin-login')
  } catch {
    router.push('/admin-login')
  }
}

onMounted(() => {
  loadCurrentStatus()
  loadUsers()
  loadAnnouncements()
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
