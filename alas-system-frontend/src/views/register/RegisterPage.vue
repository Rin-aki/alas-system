<template>
  <div class="register-container">
    <div class="glass-panel super-glass animate-entry">
      <div class="header">
        <h2>加入 ALAS</h2>
        <p class="subtitle">创建您的管理账号</p>
      </div>

      <el-form
        ref="registerFormRef"
        :model="ruleForm"
        status-icon
        :rules="rules"
        class="register-form"
        size="large"
        label-width="0"
      >
        <el-form-item prop="email">
          <el-input 
            v-model="ruleForm.email" 
            placeholder="请输入邮箱"
            :prefix-icon="Message"
          />
        </el-form-item>

        <el-form-item prop="pass">
          <el-input
            type="password"
            v-model="ruleForm.pass"
            placeholder="设置密码"
            autocomplete="off"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>

        <el-form-item prop="checkPass">
          <el-input
            type="password"
            v-model="ruleForm.checkPass"
            placeholder="确认密码"
            autocomplete="off"
            show-password
            :prefix-icon="Key"
            @keyup.enter="submitForm"
          />
        </el-form-item>

        <div class="btn-group">
          <el-button 
            type="primary" 
            @click="submitForm" 
            :loading="loading"
            class="submit-btn" 
            round
          >
            立即注册
          </el-button>
          
          <div class="login-link">
            <router-link to="/login">
              已有账号？返回登录
            </router-link>
          </div>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Message, Lock, Key } from '@element-plus/icons-vue'
import { userService } from '../../services/api.js'

const router = useRouter()
const loading = ref(false)
const registerFormRef = ref(null)

// 表单数据
const ruleForm = reactive({
  email: "",
  pass: "",       // 实际密码
  checkPass: "",  // 确认密码 (原代码叫 password，这里改名以免混淆)
})

// 验证逻辑：验证第一次输入的密码
const validatePass = (rule, value, callback) => {
  if (value === "") {
    callback(new Error("请输入密码"))
  } else {
    if (ruleForm.checkPass !== "") {
      if (registerFormRef.value) {
        registerFormRef.value.validateField("checkPass")
      }
    }
    callback()
  }
}

// 验证逻辑：验证两次密码是否一致
const validatePass2 = (rule, value, callback) => {
  if (value === "") {
    callback(new Error("请再次输入密码"))
  } else if (value !== ruleForm.pass) {
    callback(new Error("两次输入密码不一致!"))
  } else {
    callback()
  }
}

// 验证规则
const rules = {
  email: [
    { required: true, message: "邮箱不能为空！", trigger: "blur" },
    { type: 'email', message: "请输入正确的邮箱格式", trigger: "blur" }
  ],
  pass: [
    { required: true, validator: validatePass, trigger: "blur" },
    { min: 6, message: "密码长度不能少于6位", trigger: "blur" }
  ],
  checkPass: [
    { required: true, validator: validatePass2, trigger: "blur" },
  ],
}

const getRegisterErrorMessage = (response) => {
  return response?.data?.detail
    || response?.data?.error
    || response?.data?.message
    || '注册失败，请稍后重试'
}

// 提交表单
const submitForm = async () => {
  if (!registerFormRef.value) return
  
  await registerFormRef.value.validate((valid) => {
    if (valid) {
      loading.value = true
      
      userService.register({
        email: ruleForm.email,
        password: ruleForm.pass // 发送给后端的是 pass 字段
      })
      .then(response => {
        if (response.status === 200) {
          ElMessage.success(response.data.msg || '注册成功，请查收邮件激活账户')
          // 稍微延迟跳转，提升体验
          setTimeout(() => {
            router.push('/login')
          }, 1500)
        } else {
          ElMessage.error(getRegisterErrorMessage(response))
        }
      })
      .catch(error => {
        console.error('注册请求错误:', error)
        ElMessage.error('网络错误，请稍后重试')
      })
      .finally(() => {
        loading.value = false
      })
    } else {
      ElMessage.warning('请检查输入项')
      return false
    }
  })
}

const goBack = () => {
  router.push('/login')
}
</script>

<style scoped>
.register-container {
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
  font-size: 2.2em;
  margin: 0;
  background: linear-gradient(120deg, #a1c4fd 0%, #c2e9fb 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 2px;
  font-weight: 800;
}

.subtitle {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 0.95em;
}

.register-form {
  width: 100%;
}

/* 按钮组样式 */
.btn-group {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 15px;
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

.login-link {
  text-align: center;
}

.login-link a {
  color: var(--primary-color);
  font-size: 14px;
  text-decoration: none;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.login-link a:hover {
  opacity: 1;
  text-decoration: underline;
}
</style>
