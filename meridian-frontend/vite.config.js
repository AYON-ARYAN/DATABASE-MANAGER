import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5001',
      '/admin': 'http://localhost:5001',
      '/databases': 'http://localhost:5001',
      '/export': 'http://localhost:5001',
      '/dry-run': 'http://localhost:5001',
      '/refine': 'http://localhost:5001',
      '/analyze': 'http://localhost:5001',
      '/analyze-csv': 'http://localhost:5001',
    }
  }
})
