<template>
  <div>
    <el-card class="box-card">
      <h2>登录</h2>
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
        </el-form-item>
      </el-form>
      <div class="btnGroup">
        <el-button type="primary" @click="submitForm('ruleForm')"
          >登录</el-button>
        <el-button @click="resetForm('ruleForm')">重置</el-button>
        <router-link to="/register">
          <el-button style="margin-left:10px">注册</el-button>
        </router-link>
      </div>
    </el-card>
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
    resetForm(formName) {
      this.$refs[formName].resetFields();
    },
  },
};
</script>

<style scoped>
.box-card {
  margin: auto auto;
  width: 400px;
}
.login-from {
  margin: auto auto;
}
</style>
