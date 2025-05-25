import { createRouter, createWebHistory } from 'vue-router'

import Login from '../views/login/LoginPage.vue'
import Register from '../views/register/RegisterPage.vue'
import Dashboard from '../views/DashBoard/DashBoard.vue'
import { userService } from '../services/api.js';
const routes = [
  { path: '/login', name: 'LoginPage', component: Login, meta: { requiresAuth: false } },
  { path: '/', redirect: '/login' },
  { path: '/register', name: 'RegisterPage', component: Register, meta: { requiresAuth: false } },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard, meta: { requiresAuth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局前置守卫
router.beforeEach(async (to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);
  console.info('登录状态检查检测');
  try {
    
    const res = await userService.authcheck();

    const isAuthenticated = res.ok && res.data.is_authenticated;

    if (requiresAuth && !isAuthenticated) {
      // 需要认证但未登录
      console.info('未登录')
      next('/login');
    } else if (!requiresAuth && isAuthenticated && (to.path === '/login' || to.path === '/register')) {
      // 已登录但访问登录或注册页
      console.info('已登录，跳转')
      next('/dashboard');
    } else {
      // 其他情况正常跳转
      next();
    }
  } catch (err) {
    console.error('登录状态检查失败:', err);
    if (requiresAuth) {
      next('/login');
    } else {
      next();
    }
  }
});

export default router