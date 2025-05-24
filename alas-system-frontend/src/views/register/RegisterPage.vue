<template>
  <div>
    <el-card class="box-card">
      <h2>注册</h2>
      <el-form
        :model="ruleForm"
        status-icon
        :rules="rules"
        ref="ruleForm"
        label-position="left"
        label-width="80px"
        class="demo-ruleForm"
      >
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="ruleForm.email"></el-input>
        </el-form-item>
        <el-form-item label="密码" prop="pass">
          <el-input
            type="password"
            v-model="ruleForm.pass"
            autocomplete="off"
          ></el-input>
        </el-form-item>
        <el-form-item label="确认密码" prop="password">
          <el-input
            type="password"
            v-model="ruleForm.password"
            autocomplete="off"
          ></el-input>
        </el-form-item>
      </el-form>
      <div class="btnGroup">
        <el-button type="primary" @click="submitForm('ruleForm')"
          >提交</el-button
        >
        <el-button @click="resetForm('ruleForm')">重置</el-button>
        <el-button @click="goBack">返回</el-button>
      </div>
    </el-card>
  </div>
</template>

<script>
import { userService } from '../../services/api.js';

export default {
  data() {
    var validatePass = (rule, value, callback) => {
      if (value === "") {
        callback(new Error("请输入密码"));
      } else {
        if (this.ruleForm.checkPass !== "") {
          this.$refs.ruleForm.validateField("checkPass");
        }
        callback();
      }
    };
    var validatePass2 = (rule, value, callback) => {
      if (value === "") {
        callback(new Error("请再次输入密码"));
      } else if (value !== this.ruleForm.pass) {
        callback(new Error("两次输入密码不一致!"));
      } else {
        callback();
      }
    };
    return {
      ruleForm: {
        email: "",
        pass: "",
        password: "",
      },
      rules: {
        email: [
          { required: true, message: "邮箱不能为空！", trigger: "blur" },
          { type: 'email', message: "请输入正确的邮箱格式", trigger: "blur" }
        ],
        pass: [{ required: true, validator: validatePass, trigger: "blur" }],
        password: [
          { required: true, validator: validatePass2, trigger: "blur" },
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
            text: '注册中...',
            spinner: 'el-icon-loading',
            background: 'rgba(0, 0, 0, 0.7)'
          });
          
          // 使用API服务发送注册请求
          userService.register({
            email: this.ruleForm.email,
            password: this.ruleForm.pass
          })
          .then(response => {
            loading.close();
            
            if (response.status === 200) {
              // 注册成功
              this.$message.success(response.data.msg || '注册成功，请查收邮件激活账户');
              // 跳转到登录页
              this.$router.push('/login');
            } else {
              // 注册失败
              this.$message.error(response.data.error || '注册失败，请稍后重试');
            }
          })
          .catch(error => {
            loading.close();
            console.error('注册请求错误:', error);
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
    goBack() {
      this.$router.go(-1);
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
