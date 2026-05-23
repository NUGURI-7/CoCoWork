/// <reference types="vite/client" />

// @fontsource/* 是纯 CSS 副作用导入，不带类型声明；
// 在 noUncheckedSideEffectImports 严格模式下需声明模块以通过类型检查。
declare module '@fontsource/*'

// ldrs 基于 Web Components，需声明 JSX intrinsic elements。
declare namespace React.JSX {
  interface IntrinsicElements {
    'l-ring': {
      size?: string | number
      stroke?: string | number
      'bg-opacity'?: string | number
      speed?: string | number
      color?: string
    }
  }
}

