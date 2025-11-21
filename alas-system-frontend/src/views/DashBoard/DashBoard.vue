<template>
  <div class="glass-panel">
    <h2>欢迎使用ALAS管理系统</h2>
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

    <div class="button-group">
      <el-button type="primary" @click="linkblhx">连接实例</el-button>
      <el-button type="success" @click="linkalas">连接Alas</el-button>
      <el-button type="warning" @click="reconnect" :loading="reconnecting">重连服务</el-button>
      <el-button type="danger" @click="fix">疑难修复</el-button>
    </div>

    <div class="logout-section">
      <el-button type="danger" @click="logout">登出</el-button>
    </div>
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
      loading: false,
      reconnecting: false
    };
  },
  created() {
    this.initUser();
    this.getPurchaseStatus();
  },
  methods: {
    // 初始化用户信息
    initUser() {
      userService.authcheck()
        .then(response => {
          if (response.ok) {
            this.user.email = localStorage.getItem('email') || '未知邮箱';
            this.user.id = localStorage.getItem('user_id') || '未知ID';
            this.user.blhx_port = localStorage.getItem('blhx_port') || '未知碧蓝航线端口';
            this.user.device_ip = localStorage.getItem('device_ip') || '未知设备IP';
            this.user.alas_port = localStorage.getItem('alas_port') || '未知alas端口';
          } else {
            this.$router.push('/login');
          }
        })
        .catch(() => {
          this.$router.push('/login');
        });
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
    
    // 格式化日期
    formatDate(dateString) {
      if (!dateString) return '无';
      const date = new Date(dateString);
      return date.toLocaleString();
    },
    // 连接实例
    linkblhx() {
      if (!this.purchaseStatus.has_purchased) {
          this.$message.warning('您尚未购买服务，无法连接实例');
          return;
        }
        this.loading = true;

        const userId = localStorage.getItem('user_id');
        if (!userId) {
          this.$message.error('用户ID未找到，无法跳转');
          this.loading = false;
          return;
        }

      const url = `https://scrcpy.gjiang.xyz:58000/`;
      window.location.href = url; // 跳转到动态子域名的外部网页
    },
    linkalas() {
      if (!this.purchaseStatus.has_purchased) {
          this.$message.warning('您尚未购买服务，无法连接实例');
          return;
        }
        this.loading = true;

        const userId = localStorage.getItem('user_id');
        if (!userId) {
          this.$message.error('用户ID未找到，无法跳转');
          this.loading = false;
          return;
        }

      const url = `https://alas.gjiang.xyz:58000/`;
      window.location.href = url; // 跳转到动态子域名的外部网页
    },
    fix(){
      if (!this.purchaseStatus.has_purchased) {
          this.$message.warning('您尚未购买服务，无法进行疑难修复');
          return;
        }
        this.loading = true;

        const userId = localStorage.getItem('user_id');
        if (!userId) {
          this.$message.error('用户ID未找到，无法跳转');
          this.loading = false;
          return;
        }

      this.$router.push('/fix')
    },
    
    // 重连服务
    async reconnect() {
      if (!this.purchaseStatus.has_purchased) {
        this.$message.warning('您尚未购买服务，无法重连服务');
        return;
      }
      
      this.reconnecting = true;
      
      try {
        const response = await userService.reconnect();
        
        if (response.status === 200 && response.data.success) {
          this.$message.success(response.data.message || 'WebSocket服务重启成功！');
        } else if (response.status === 200 && !response.data.success) {
          this.$message.error(response.data.message || 'WebSocket服务重启失败');
          if (response.data.error) {
            console.error('重启错误:', response.data.error);
          }
        } else if (response.status === 401) {
          this.$message.error('登录状态已过期，请重新登录');
          this.logout();
        } else {
          this.$message.error(`重连失败 (状态码: ${response.status})`);
        }
      } catch (error) {
        console.error('重连服务错误:', error);
        this.$message.error('网络错误，请稍后重试');
      } finally {
        this.reconnecting = false;
      }
    },
    // 登出
    async logout() {
      try {
        // 先清理本地存储
        localStorage.removeItem('user_id');
        localStorage.removeItem('email');
        localStorage.removeItem('ip');
        localStorage.removeItem('blhx_port');
        localStorage.removeItem('device_ip');
        localStorage.removeItem('alas_port');
        
        // 调用后端登出API并等待完成
        await userService.logout();
        
        this.$message.success('已成功登出');
        
        // 使用 replace 而不是 push，避免路由历史问题
        // 添加一个小延迟确保后端状态更新
        setTimeout(() => {
          this.$router.replace('/login');
        }, 100);
        
      } catch (error) {
        console.error('登出过程中出现错误:', error);
        // 即使出错也要清理状态并跳转
        this.$message.success('已成功登出');
        this.$router.replace('/login');
      }
    }
  }
};
</script>

<style scoped>
.glass-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 600px;
  max-height: 80vh;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  background-color: rgba(255, 255, 255, 0.2);
  box-shadow: rgba(0, 0, 0, 0.1) 0px 4px 6px, rgba(0, 0, 0, 0.1) 0px 1px 3px;
  z-index: 2;
  padding: 40px;
  text-align: center;
  overflow-y: auto;
}

.glass-panel h2 {
  margin-bottom: 20px;
  color: #333;
}

.glass-panel p {
  margin: 10px 0;
  color: #555;
}

.purchase-info {
  margin: 20px 0;
  padding: 15px;
  background-color: rgba(248, 249, 250, 0.6);
  border-radius: 5px;
  backdrop-filter: blur(5px);
}

.purchase-info h3 {
  margin-bottom: 10px;
  color: #333;
}

.purchase-details {
  margin-top: 10px;
}

.purchase-details p {
  margin: 5px 0;
  color: #555;
}

.button-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 20px 0;
  flex-wrap: wrap;
}

.logout-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(238, 238, 238, 0.5);
}
</style>
