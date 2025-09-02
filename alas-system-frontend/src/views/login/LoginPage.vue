<template>
  <div class="glass-panel">
    <h2>ALAS管理系统</h2>
    <el-form
      :model="ruleForm"
      status-icon
      :rules="rules"
      ref="ruleForm"
      label-position="left"
      label-width="70px"
      class="login-from"
    >
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="ruleForm.email"></el-input>
      </el-form-item>
      <el-form-item label="密码" prop="password">
        <el-input
          type="password"
          v-model="ruleForm.password"
          autocomplete="off"
        ></el-input>
        <div class="register-link">
          <router-link to="/register">
            <span>第一次使用？前往注册</span>
          </router-link>
        </div>
      </el-form-item>
    </el-form>
    <div class="btnGroup">
      <el-button type="primary" @click="submitForm('ruleForm')" style="width: 100%">登录</el-button>
    </div>
  </div>
</template>

<script>
import { userService } from '../../services/api.js';

export default {
  data() {
    return {
      ruleForm: {
        email: "",
        password: "",
      },
      rules: {
        email: [
          { required: true, message: "邮箱不能为空！", trigger: "blur" },
          { type: 'email', message: "请输入正确的邮箱格式", trigger: "blur" }
        ],
        password: [
          { required: true, message: "密码不能为空！", trigger: "blur" },
        ],
      },
    };
  },

  methods: {
    submitForm(formName) {
      this.$refs[formName].validate((valid) => {
        if (valid) {
          // 显示加载状态
          const loading = this.$loading({
            lock: true,
            text: '登录中...',
            spinner: 'el-icon-loading',
            background: 'rgba(0, 0, 0, 0.7)'
          });
          
          // 使用API服务发送登录请求
          userService.login({
            email: this.ruleForm.email,
            password: this.ruleForm.password
          })
          .then(response => {
            loading.close();
            
            if (response.status === 200) {
              // 登录成功
              this.$message.success(response.data.msg || '登录成功');
              
              // 保存令牌到本地存储
              localStorage.setItem('user_id', response.data.user_id);
              localStorage.setItem('email', response.data.email);
              localStorage.setItem('ip', response.data.ip);
              console.log(response.data.email)
              
              // 跳转到仪表盘
              this.$router.push('/dashboard');
            } else if (response.status === 403) {
              // 账户未激活
              this.$message.warning(response.data.error || '账户未激活，请查收邮件进行激活');
            } else {
              // 登录失败
              this.$message.error(response.data.error || '邮箱或密码错误');
            }
          })
          .catch(error => {
            loading.close();
            console.error('登录请求错误:', error);
            this.$message.error('网络错误，请稍后重试');
          });
        } else {
          console.log("表单验证失败");
          return false;
        }
      });
    },
    goToRegister() {
      this.$router.push('/register');
    }
  },
};
</script>

<style scoped>
.glass-panel {
  position: fixed;
  top: 0;
  left: 5%;
  width: 20%;
  height: 100vh;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  background-color: rgba(255, 255, 255, 0.2);
  box-shadow: rgba(0, 0, 0, 0.1) 0px 4px 6px, rgba(0, 0, 0, 0.1) 0px 1px 3px;
  z-index: 2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 40px;
  margin: 0;
}

/* 手机端适配 */
@media (max-width: 768px) {
  .glass-panel {
    left: 0;
    width: 100%;
    padding: 20px;
  }
}

/* 平板端适配 */
@media (min-width: 769px) and (max-width: 1024px) {
  .glass-panel {
    left: 2%;
    width: 40%;
    padding: 30px;
  }
}

.glass-panel h2 {
  text-align: center;
  margin-bottom: 20px;
  color: #333;
}

.login-from {
  width: 100%;
  max-width: 400px;
}

.btnGroup {
  width: 100%;
  max-width: 400px;
  margin-top: 20px;
}

.register-link {
  text-align: right;
  margin-top: 10px; /* 增加与密码框的间距 */
  width: 100%;
}

.register-link span {
  color: #409eff;
  cursor: pointer;
  text-decoration: none;
  transition: color 0.3s;
}

.register-link span:hover {
  color: #66b1ff;
  text-decoration: underline;
}

/* 手机端注册链接样式调整 */
@media (max-width: 768px) {
  .register-link {
    text-align: center;
    font-size: 14px;
    margin-bottom: 20px;
  }
}
</style>