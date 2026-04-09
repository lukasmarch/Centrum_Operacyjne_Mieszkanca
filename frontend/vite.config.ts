import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { videoFFmpegPlugin } from './vite-plugin-video-ffmpeg';

export default defineConfig(({ mode }) => {
  // Load .env from backend directory
  const env = loadEnv(mode, path.resolve(__dirname, '../backend'), '');

  return {
    envDir: path.resolve(__dirname, '../backend'),
    server: {
      port: 3001,
      host: '0.0.0.0',
    },
    plugins: [
      react(),
      videoFFmpegPlugin({
        outputDir: 'public/videos',
        videos: [
          {
            // kula_2.mp4: sampled bg = #091223 (rgb 9,18,35), page bg = #05080f (rgb 5,8,15)
            input: '../assets/kula_2.mp4',
            name: 'kula',
            crfMp4: 20,
            crfWebm: 32,
            colorMatch: {
              sourceBg: { r: 9, g: 18, b: 35 },
              targetBg: { r: 5, g: 8,  b: 15 },
              midtoneAnchor: 0.22,
            },
            vignette: Math.PI / 4.5,
          },
        ],
      }),
      VitePWA({
        registerType: 'autoUpdate',
        strategies: 'injectManifest',
        srcDir: 'src',
        filename: 'sw.ts',
        manifest: {
          name: 'Centrum Operacyjne Mieszkańca',
          short_name: 'CentrumMieszkanca',
          description: 'Informacje lokalne dla gminy Rybno i powiatu działdowskiego',
          theme_color: '#2563eb',
          background_color: '#ffffff',
          display: 'standalone',
          start_url: '/',
          icons: [
            { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
          ],
        },
        devOptions: {
          enabled: true,
          type: 'module',
        },
      }),
    ],
    define: {
      'import.meta.env.VITE_API_URL': JSON.stringify(env.API_URL || 'http://localhost:8000/api')
    },
    build: {
      sourcemap: false,
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      }
    }
  };
});
