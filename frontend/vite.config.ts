import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Load environment variables from project root (.env)
  const envDir = new URL('..', import.meta.url).pathname;
  const env = loadEnv(mode, envDir, '');

  const host = env.HOST || '127.0.0.1';
  const frontendPort = parseInt(env.FRONTEND_PORT || '5173', 10);
  const backendHost = env.HOST || '127.0.0.1';
  const backendPort = env.BACKEND_PORT || '8000';

  return {
    plugins: [react()],
    server: {
      host,
      port: frontendPort,
      proxy: {
        '/api': {
          target: `http://${backendHost}:${backendPort}`,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  };
});
