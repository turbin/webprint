import { createApp } from 'vue'
import App from './App.vue'

console.log('开始创建Vue应用实例')

// 创建应用实例
const app = createApp(App)

// 添加全局错误处理
app.config.errorHandler = (err) => {
  console.error('Vue错误:', err)
}

console.log('准备挂载Vue应用')

// 挂载应用
app.mount('#app')

console.log('Vue应用挂载完成') 