<template>
  <div class="login-container">
    <div class="glass-panel super-glass animate-entry">
      <div class="header">
        <h1>ALAS</h1>
        <p class="subtitle">管理系统登录</p>
      </div>
      
      <el-form
        ref="loginFormRef"
        :model="ruleForm"
        :rules="rules"
        class="login-form"
        size="large"
      >
        <el-form-item prop="email">
          <el-input 
            v-model="ruleForm.email" 
            placeholder="请输入邮箱"
            :prefix-icon="Message"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            type="password"
            v-model="ruleForm.password"
            placeholder="请输入密码"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="submitForm"
          />
        </el-form-item>

        <div class="form-footer">
           <router-link to="/register" class="link-text">
             没有账号？立即注册
           </router-link>
        </div>

        <el-button 
          type="primary" 
          :loading="isLoading"
          @click="submitForm" 
          class="submit-btn"
          round
        >
          登 录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Message, Lock } from '@element-plus/icons-vue'
import { userService } from '../../services/api.js'

const router = useRouter()
// 表单数据对象
const ruleForm = reactive({ email: "", password: "" })
// 修复点3：定义唯一的表单引用变量
const loginFormRef = ref(null)
const isLoading = ref(false)

const rules = {
  email: [
    { required: true, message: "邮箱不能为空", trigger: "blur" },
    { type: 'email', message: "格式不正确", trigger: "blur" }
  ],
  password: [
    { required: true, message: "密码不能为空", trigger: "blur" },
  ]
}

const persistUserProfile = (profile) => {
  localStorage.setItem('user_id', profile.user_id ?? '')
  localStorage.setItem('email', profile.email ?? '')
  localStorage.setItem('ip', profile.alas_ip ?? '')
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
    const response = await userService.login({
      email: ruleForm.email,
      password: ruleForm.password
    })

    console.log("登录响应:", response)

    if (response.status === 200) {
      const sessionReady = await userService.waitForSession()

      if (!sessionReady) {
        ElMessage.error('登录成功，但会话尚未确认，请稍后重试')
        return
      }

      const userInfoResponse = await userService.getUserInfo().catch(() => null)
      const profile = userInfoResponse?.ok ? userInfoResponse.data : response.data

      persistUserProfile(profile)
      ElMessage.success(response.data.msg || '欢迎回来')
      await router.replace('/dashboard')
      return
    }

    if (response.status === 403) {
      ElMessage.warning(response.data.error || response.data.detail || '账户未激活')
      return
    }

    ElMessage.error(response.data.error || response.data.detail || '登录失败')
  } catch (err) {
    console.error('API错误:', err)
    ElMessage.error('网络连接异常或服务器错误')
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
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
  margin-bottom: 40px;
}

.header h1 {
  font-size: 3em;
  margin: 0;
  background: linear-gradient(120deg, #a1c4fd 0%, #c2e9fb 100%);
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
  background: linear-gradient(90deg, #409eff, #36d1dc);
  border: none;
  transition: transform 0.2s, box-shadow 0.2s;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(64, 158, 255, 0.4);
}
</style>
