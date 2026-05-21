import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import '@fontsource/instrument-serif' // self-host Instrument Serif（400 normal）
import './app.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
