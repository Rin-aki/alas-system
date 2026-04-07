<template>
  <div class="admin-login-container">
    <div class="glass-panel super-glass animate-entry">
      <div class="header">
        <h1>ADMIN</h1>
        <p class="subtitle">管理员控制台</p>
      </div>

      <el-form
        ref="loginFormRef"
        :model="ruleForm"
        :rules="rules"
        class="login-form"
        size="large"
      >
        <el-form-item prop="username">
          <el-input
            v-model="ruleForm.username"
            placeholder="请输入管理员账号"
            :prefix-icon="User"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            type="password"
            v-model="ruleForm.password"
            placeholder="请输入管理员密码"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="submitForm"
          />
        </el-form-item>

        <div class="form-footer">
          <router-link to="/login" class="link-text">
            返回用户登录
          </router-link>
        </div>

        <el-button
          type="danger"
          :loading="isLoading"
          @click="submitForm"
          class="submit-btn"
          round
        >
          管理员登录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { adminService } from '../../services/api.js'

const router = useRouter()
const ruleForm = reactive({ username: "", password: "" })
const loginFormRef = ref(null)
const isLoading = ref(false)

const rules = {
  username: [
    { required: true, message: "管理员账号不能为空", trigger: "blur" }
  ],
  password: [
    { required: true, message: "管理员密码不能为空", trigger: "blur" }
  ]
}

const submitForm = async () => {
  if (!loginFormRef.value) {
    console.error("表单实例未找到")
    return
  }

  try {
    await loginFormRef.value.validate()
  } catch (fields) {
    console.log('表单验证失败', fields)
    ElMessage.warning('请检查输入项')
    return
  }

  isLoading.value = true

  try {
    const response = await adminService.login({
      username: ruleForm.username,
      password: ruleForm.password
    })

    console.log("管理员登录响应:", response)

    if (response.ok) {
      const sessionReady = await adminService.waitForSession()

      if (!sessionReady) {
        ElMessage.error('登录成功，但会话尚未确认，请稍后重试')
        return
      }

      ElMessage.success(response.data.msg || '管理员登录成功')
      await router.replace('/admin')
      return
    }

    ElMessage.error(response.data.detail || '登录失败，请检查账号密码')
  } catch (err) {
    console.error('API错误:', err)
    ElMessage.error('网络连接异常或服务器错误')
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.admin-login-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
  margin-bottom: 40px;
}

.header h1 {
  font-size: 3em;
  margin: 0;
  background: linear-gradient(120deg, #ff6b6b 0%, #ff8787 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 4px;
  font-weight: 800;
}

.subtitle {
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: 1.1em;
  letter-spacing: 2px;
}

.login-form {
  width: 100%;
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 20px;
}

.link-text {
  color: var(--primary-color);
  font-size: 14px;
  text-decoration: none;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.link-text:hover {
  opacity: 1;
  text-decoration: underline;
}

.submit-btn {
  width: 100%;
  font-weight: bold;
  font-size: 16px;
  padding: 22px 0;
  background: linear-gradient(90deg, #ff6b6b, #ee5a6f);
  border: none;
  transition: transform 0.2s, box-shadow 0.2s;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(255, 107, 107, 0.4);
}
</style>
