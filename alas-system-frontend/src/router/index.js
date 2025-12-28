import { createRouter, createWebHistory } from 'vue-router'

import Login from '../views/login/LoginPage.vue'
import Register from '../views/register/RegisterPage.vue'
import Dashboard from '../views/DashBoard/DashBoard.vue'
import fixPage from '../views/fix/fixPage.vue'
import AdminPanel from '../views/admin/AdminPanel.vue'
import { userService } from '../services/api.js';
const routes = [
  { path: '/login', name: 'LoginPage', component: Login, meta: { title: 'AlasMan - 登录', requiresAuth: false } },
  { path: '/', redirect: '/login' },
  { path: '/register', name: 'RegisterPage', component: Register, meta: { title: 'AlasMan - 注册',requiresAuth: false } },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard, meta: { title: 'AlasMan - 控制台',requiresAuth: true } },
  { path: '/fix', name: 'fixPage', component: fixPage, meta: { title: 'AlasMan - 疑难修复',requiresAuth: true } },
  { path: '/admin', name: 'AdminPanel', component: AdminPanel, meta: { title: 'AlasMan - 管理面板',requiresAuth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局前置守卫
router.beforeEach(async (to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);
  console.info('登录状态检查检测');

  // 设置网页标题（如果有定义）
  if (to.meta && to.meta.title) {
    document.title = to.meta.title;
  }

  try {
    const res = await userService.authcheck();
    const isAuthenticated = res.ok && res.data.is_authenticated;

    if (requiresAuth && !isAuthenticated) {
      console.info('未登录');
      next('/login');
    } else if (!requiresAuth && isAuthenticated && (to.path === '/login' || to.path === '/register')) {
      console.info('已登录，跳转');
      next('/dashboard');
    } else {
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