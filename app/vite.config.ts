import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          const normalized = id.replace(/\\/g, '/')
          if (normalized.includes('/node_modules/react/') || normalized.includes('/node_modules/react-dom/')) {
            return 'vendor-react'
          }
          if (normalized.includes('/node_modules/lucide-react/')) {
            return 'vendor-icons'
          }
        },
      },
    },
  },
})



