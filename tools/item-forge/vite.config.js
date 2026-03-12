import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5220,
    strictPort: true,
    open: true,
    proxy: {
      '/api': 'http://localhost:5221',
    },
  },
  build: {
    outDir: 'dist',
  },
});
