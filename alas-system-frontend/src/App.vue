<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

// 背景样式的响应式数据
const globalBackgroundStyle = ref({
  backgroundImage: ''
})

// 定时器引用
let backgroundTimer = null

// 设置全局背景的函数
const setGlobalBackground = () => {
  const hours = new Date().getHours()
  let bgImage = ''

  if (hours >= 18 || hours < 6) {
    // 18点到第二天6点 - 夜晚
    bgImage = 'url("/night.png")'
  } else if (hours >= 6 && hours < 9) {
    // 6点到9点 - 清晨
    bgImage = 'url("/twilight.png")'
  } else if (hours >= 9 && hours < 16) {
    // 9点到16点 - 白天
    bgImage = 'url("/day.png")'
  } else if (hours >= 16 && hours < 18) {
    // 16点到18点 - 傍晚
    bgImage = 'url("/twilight.png")'
  }

  globalBackgroundStyle.value.backgroundImage = bgImage
}

// 组件挂载时初始化
onMounted(() => {
  setGlobalBackground()
  // 每小时检查一次时间，自动切换背景
  backgroundTimer = setInterval(() => {
    setGlobalBackground()
  }, 60000 * 60) // 每小时检查一次
})

// 组件卸载时清理定时器
onUnmounted(() => {
  if (backgroundTimer) {
    clearInterval(backgroundTimer)
  }
})
</script>

<template>
  <div id="app" :style="globalBackgroundStyle">
    <router-view />
  </div>
</template>
  
<style>
/* 全局样式重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  overflow-x: hidden;
}

#app {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  background-attachment: fixed;
  overflow-y: auto; /* 允许垂直滚动 */
  overflow-x: hidden; /* 禁止水平滚动 */
}

/* 原有的logo样式保持不变 */
.logo {
  height: 6em;
  padding: 1.5em;
  will-change: filter;
  transition: filter 300ms;
}

.logo:hover {
  filter: drop-shadow(0 0 2em #646cffaa);
}

.logo.vue:hover {
  filter: drop-shadow(0 0 2em #42b883aa);
}
</style>