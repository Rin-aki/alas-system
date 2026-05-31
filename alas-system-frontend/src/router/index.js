import { createRouter, createWebHistory } from 'vue-router'

import Login from '../views/login/LoginPage.vue'
import Register from '../views/register/RegisterPage.vue'
import Dashboard from '../views/DashBoard/DashBoard.vue'
import fixPage from '../views/fix/fixPage.vue'
import DevicePage from '../views/device/DevicePage.vue'
import AdminLogin from '../views/admin/AdminLogin.vue'
import AdminPanel from '../views/admin/AdminPanel.vue'
import VerifyEmail from '../views/verify-email/VerifyEmailPage.vue'
import { userService, adminService } from '../services/api.js';
const routes = [
  { path: '/login', name: 'LoginPage', component: Login, meta: { title: 'AlasMan - 登录', requiresAuth: false } },
  { path: '/', redirect: '/login' },
  { path: '/register', name: 'RegisterPage', component: Register, meta: { title: 'AlasMan - 注册', requiresAuth: false } },
  { path: '/verify-email', name: 'VerifyEmail', component: VerifyEmail, meta: { title: 'AlasMan - 邮箱验证', requiresAuth: false } },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard, meta: { title: 'AlasMan - 控制台', requiresAuth: true } },
  { path: '/fix', name: 'fixPage', component: fixPage, meta: { title: 'AlasMan - 疑难修复', requiresAuth: true } },
  { path: '/device', name: 'DevicePage', component: DevicePage, meta: { title: 'AlasMan - 设备控制', requiresAuth: true } },
  { path: '/admin-login', name: 'AdminLogin', component: AdminLogin, meta: { title: 'AlasMan - 管理员登录', requiresAuth: false, requiresAdmin: false } },
  { path: '/admin', name: 'AdminPanel', component: AdminPanel, meta: { title: 'AlasMan - 管理面板', requiresAuth: false, requiresAdmin: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局前置守卫
router.beforeEach(async (to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);
  const requiresAdmin = to.matched.some(record => record.meta.requiresAdmin);

  // 设置网页标题（如果有定义）
  if (to.meta && to.meta.title) {
    document.title = to.meta.title;
  }

  // 管理员路由守卫
  if (requiresAdmin) {
    console.info('管理员权限检查');
    try {
      const isAdmin = await adminService.isAuthenticated();

      if (!isAdmin) {
        console.info('非管理员，跳转到管理员登录');
        next('/admin-login');
      } else {
        // 已登录管理员，如果访问管理员登录页则跳转到管理面板
        if (to.path === '/admin-login') {
          next('/admin');
        } else {
          next();
        }
      }
    } catch (err) {
      console.error('管理员状态检查失败:', err);
      next('/admin-login');
    }
    return;
  }

  // 普通用户路由守卫
  if (requiresAuth) {
    console.info('登录状态检查检测');
    try {
      const isAuthenticated = await userService.isAuthenticated();

      if (!isAuthenticated) {
        console.info('未登录');
        next('/login');
      } else {
        next();
      }
    } catch (err) {
      console.error('登录状态检查失败:', err);
      next('/login');
    }
    return;
  }

  // 对于不需要认证的页面
  try {
    const isAuthenticated = await userService.isAuthenticated();

    if (isAuthenticated && (to.path === '/login' || to.path === '/register')) {
      console.info('已登录，跳转到控制台');
      next('/dashboard');
    } else {
      next();
    }
  } catch (err) {
    // 检查失败，允许访问公开页面
    next();
  }
});


export default router
