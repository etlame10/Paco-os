import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base './' -> rutas relativas: funciona en GitHub Pages (usuario.github.io/repo/)
// y en cualquier otro hosting estático sin tocar nada.
export default defineConfig({
  plugins: [react()],
  base: './',
})
