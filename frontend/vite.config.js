import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        // In docker-compose, this dev server runs inside its own container,
        // so `localhost` refers to that container -- reach the backend
        // service by its compose service name instead. Overridable for
        // running the frontend outside docker (e.g. `npm run dev` directly).
        target: process.env.VITE_API_PROXY_TARGET || 'http://backend:5000',
        changeOrigin: true,
      },
    },
  },
})
