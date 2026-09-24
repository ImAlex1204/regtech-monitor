import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 相對路徑：GitHub Pages 掛在 /regtech-monitor/ 底下，本機 FastAPI 掛在 / 底下，同一份 build 兩邊都能用
  base: './',
  server: {
    // 開發時 /api 轉給本機 FastAPI（api.py）；沒開 API 時前端自動退回 Demo 模式讀靜態 JSON
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
