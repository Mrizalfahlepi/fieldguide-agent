import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: ['unsickered-bill-incomprehensively.ngrok-free.dev'],
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
