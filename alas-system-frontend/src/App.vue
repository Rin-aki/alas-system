<script setup>
// 不需要任何 JS 逻辑了，纯 CSS 驱动
</script>

<template>
  <div id="app">
    <div class="mesh-background">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>
    
    <div class="content-wrapper">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
  </div>
</template>

<style>
/* 全局重置保持不变 */
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; overflow: hidden; }

#app {
  position: fixed;
  inset: 0;
  background-color: #0f172a; /* 深蓝底色 */
  color: white;
  font-family: 'Inter', sans-serif;
}

.content-wrapper {
  position: relative;
  z-index: 10; /* 保证内容在背景之上 */
  height: 100%;
  overflow-y: auto;
}

/* --- 核心背景样式 --- */
.mesh-background {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  z-index: 0;
  /* 这里可以调节背景模糊程度，数值越大光晕越柔和 */
  filter: blur(80px); 
}

.orb {
  position: absolute;
  border-radius: 50%;
  opacity: 0.6;
  animation: float 20s infinite ease-in-out alternate;
}

/* 光斑 1 - 蓝色系 */
.orb-1 {
  width: 60vw;
  height: 60vw;
  background: radial-gradient(circle, #3b82f6 0%, rgba(59, 130, 246, 0) 70%);
  top: -10%;
  left: -10%;
  animation-duration: 25s;
}

/* 光斑 2 - 紫色系 */
.orb-2 {
  width: 50vw;
  height: 50vw;
  background: radial-gradient(circle, #8b5cf6 0%, rgba(139, 92, 246, 0) 70%);
  bottom: -10%;
  right: -10%;
  animation-duration: 30s;
  animation-delay: -5s;
}

/* 光斑 3 - 青色系 (点缀) */
.orb-3 {
  width: 40vw;
  height: 40vw;
  background: radial-gradient(circle, #06b6d4 0%, rgba(6, 182, 212, 0) 70%);
  top: 40%;
  left: 40%;
  animation-duration: 22s;
  animation-delay: -10s;
}

@keyframes float {
  0% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(10%, 15%) scale(1.1); }
  66% { transform: translate(-5%, 5%) scale(0.9); }
  100% { transform: translate(5%, -10%) scale(1.05); }
}

/* 路由动画 */
.fade-enter-active, .fade-leave-active { transition: opacity 0.4s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>