import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import NProgress from 'nprogress'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'
import 'nprogress/nprogress.css'
import '@fontsource/instrument-serif' // self-host Instrument Serif（400 normal）
import './app.css'
import { routeTree } from './routeTree.gen'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

NProgress.configure({ showSpinner: false, easing: 'ease', speed: 400 })

const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  scrollRestoration: true,
})

// 路由切换进度条 — TanStack Router 的 status 流：pending → idle
router.subscribe('onBeforeLoad', () => NProgress.start())
router.subscribe('onLoad', () => NProgress.done())
router.subscribe('onResolved', () => NProgress.done())

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

ReactDOM.createRoot(document.getElementById('app')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
