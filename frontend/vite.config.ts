import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    // Use vmThreads instead of the default forks pool to avoid Windows
    // child-process fork timeouts that prevent workers from starting.
    pool: 'vmThreads',
    testTimeout: 30000,
    hookTimeout: 30000,
  },
})
