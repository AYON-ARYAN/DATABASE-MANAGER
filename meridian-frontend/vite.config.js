import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev-only: the SPA router uses basename="/app", so the bare dev root ("/")
// renders blank. Redirect it to "/app/" so `npm run dev` lands on the app.
// apply:'serve' => this never touches the production build.
function redirectRootToApp() {
  return {
    name: 'redirect-root-to-app',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url === '/') {
          res.writeHead(302, { Location: '/app/' })
          res.end()
          return
        }
        next()
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), redirectRootToApp()],
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
