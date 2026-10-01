import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        // Keep shared React helpers out of the landing-only renderer chunk.
        onlyExplicitManualChunks: true,
        manualChunks(id) {
          const path = id.replace(/\\/g, '/');
          if (path.includes('/node_modules/three/')) return 'three';
          if (path.includes('/node_modules/@react-three/fiber/')) return 'react-three';
          if (['react', 'react-dom', 'lucide-react', 'react-router-dom', 'react-router']
            .some((name) => path.includes(`/node_modules/${name}/`))) return 'vendor';
        },
      },
    },
  },
});
