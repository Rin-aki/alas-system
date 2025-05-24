import { createRouter, createWebHistory } from 'vue-router'

import Login from '../views/login/LoginPage.vue'
import Register from '../views/register/RegisterPage.vue'
import Dashboard from '../views/DashBoard/DashBoard.vue'

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
router.beforeEach((to, from, next) => {
  // 检查路由是否需要认证
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);
  
  // 获取当前登录状态
  const isAuthenticated = !!localStorage.getItem('token');
  
  if (requiresAuth && !isAuthenticated) {
    // 需要认证但未登录，重定向到登录页
    next('/login');
  } else if (!requiresAuth && isAuthenticated && (to.path === '/login' || to.path === '/register')) {
    // 已登录但访问登录或注册页，重定向到仪表盘
    next('/dashboard');
  } else {
    // 其他情况正常导航
    next();
  }
});

export default router