<template>
  <div class="dashboard-container">
    <el-card class="welcome-card">
      <h2>欢迎使用系统</h2>
      <p>您的邮箱: <strong>{{ user.email }}</strong></p>
      <p>您的用户ID: <strong>{{ user.id }}</strong></p>
      
      <!-- 购买状态信息 -->
      <div class="purchase-info">
        <h3>购买状态</h3>
        <el-tag v-if="purchaseStatus.has_purchased" type="success">已购买</el-tag>
        <el-tag v-else type="info">未购买</el-tag>
        
        <div v-if="purchaseStatus.has_purchased" class="purchase-details">
          <p>过期时间: {{ formatDate(purchaseStatus.purchase_expires) }}</p>
          <p>剩余天数: {{ purchaseStatus.days_remaining }} 天</p>
        </div>
      </div>
      
      <!-- 购买服务表单 -->
      <div class="purchase-form">
        <h3>购买服务</h3>
        <el-form :model="purchaseForm" label-width="100px">
          <el-form-item label="购买天数">
            <el-select v-model="purchaseForm.days" placeholder="请选择购买天数">
              <el-option label="30天" :value="30"></el-option>
              <el-option label="90天" :value="90"></el-option>
              <el-option label="180天" :value="180"></el-option>
              <el-option label="365天" :value="365"></el-option>
            </el-select>
          </el-form-item>
          <el-button type="primary" @click="purchaseService" :loading="loading">购买服务</el-button>
        </el-form>
      </div>
      
      <div>
        <el-button type="primary" @click="linkblhx">连接实例</el-button>
      </div>

      <div class="logout-section">
        <el-button type="danger" @click="logout">登出</el-button>
      </div>
    </el-card>
  </div>
</template>

<script>
import { userService } from '../../services/api.js';

export default {
  data() {
    return {
      user: {
        email: "",
        id: null,
        device_ip: "",
        blhx_port: "",
        alas_port: ""
      },
      purchaseStatus: {
        has_purchased: false,
        purchase_expires: null,
        days_remaining: 0,
        purchase_expired: false
      },
      purchaseForm: {
        days: 30
      },
      loading: false
    };
  },
  created() {
    this.initUser();
    this.getPurchaseStatus();
  },
  methods: {
    // 初始化用户信息
    initUser() {
      const token = localStorage.getItem('token');
      if (!token) {
        this.$router.push('/login');
        return;
      }
      
      this.user.email = localStorage.getItem('email') || '未知邮箱';
      this.user.id = localStorage.getItem('user_id') || '未知ID';
      this.user.blhx_port = localStorage.getItem('blhx_port') || '未知碧蓝航线端口';
      this.user.device_ip = localStorage.getItem('device_ip') || '未知设备IP';
      this.user.alas_port = localStorage.getItem('alas_port') || '未知alas端口';
    },
    
    // 获取购买状态
    getPurchaseStatus() {
      this.loading = true;
      
      userService.getPurchaseStatus()
        .then(response => {
          if (response.status === 200) {
            this.purchaseStatus = response.data;
          } else if (response.status === 422) {
            this.$message.error('登录状态已过期，请重新登录');
            this.logout();
          } else {
            this.$message.error(response.data.error || `获取购买状态失败 (状态码: ${response.status})`);
          }
        })
        .catch(error => {
          console.error('获取购买状态错误:', error);
          this.$message.error('网络错误，请稍后重试');
        })
        .finally(() => {
          this.loading = false;
        });
    },
    
    // 购买服务
    purchaseService() {
      this.loading = true;
      
      userService.purchase({ days: this.purchaseForm.days })
        .then(response => {
          if (response.ok) {
            this.$message.success('购买成功');
            this.getPurchaseStatus();
          } else {
            this.$message.error(response.data.error || '购买失败');
          }
        })
        .catch(error => {
          console.error('购买服务错误:', error);
          this.$message.error('网络错误，请稍后重试');
        })
        .finally(() => {
          this.loading = false;
        });
    },
    
    // 格式化日期
    formatDate(dateString) {
      if (!dateString) return '无';
      const date = new Date(dateString);
      return date.toLocaleString();
    },
  
    // createContainer() {
    //   if (!this.purchaseStatus.has_purchased) {
    //     this.$message.warning('您尚未购买服务，无法创建容器');
    //     return;
    //   }

    //   this.loading = true;
    //   userService.createContainer()
    //     .then(response => {
    //       if (response.ok) {
    //         this.$message.success('容器创建成功');
    //       } else {
    //         this.$message.error(response.data.error || '容器创建失败');
    //       }
    //     })
    //     .catch(error => {
    //       console.error('创建容器错误:', error);
    //       this.$message.error('网络错误，请稍后重试');
    //     })
    //     .finally(() => {
    //       this.loading = false;
    //     });
    // },
    // 连接实例
    linkblhx() {
      if (!this.purchaseStatus.has_purchased) {
        this.$message.warning('您尚未购买服务，无法连接实例');
        return;
      }
      this.loading = true;
      const baseUrl = 'https://scrcpy.gjiang.xyz:4443/'; // 外部网页的基础 URL
      // const params = new URLSearchParams({
      //   uid: this.user.device_ip+this.user.blhx_port,
      //   email: this.user.email
      // }).toString(); // 创建 URL 查询参数字符串

      // const url = `${baseUrl}?${params}`; // 拼接完整的 URL
      const url = `${baseUrl}`; // 拼接完整的 URL
      window.location.href = url; // 跳转到外部网页
    },
    // 登出
    logout() {
      localStorage.removeItem('token');
      localStorage.removeItem('user_id');
      localStorage.removeItem('email');
      this.$message.success('已成功登出');
      this.$router.push('/login');
    }
  }
};
</script>

<style scoped>
.dashboard-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
  padding: 20px;
}

.welcome-card {
  width: 600px;
  text-align: center;
}

.purchase-info {
  margin: 20px 0;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 5px;
}

.purchase-details {
  margin-top: 10px;
}

.purchase-form {
  margin: 20px 0;
  padding: 15px;
  background-color: #f0f9eb;
  border-radius: 5px;
}

.logout-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #eee;
}
</style>
