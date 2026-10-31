import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Cible du proxy de développement : surchargeable via API_PROXY_TARGET (fichier .env du frontend).
  const env = loadEnv(mode, process.cwd(), '')
  const cibleApi = env.API_PROXY_TARGET || 'http://localhost:5000'

  return {
    plugins: [react()],
    server: {
      // Le frontend appelle "/api/..." et affiche "/uploads/..." : Vite relaie vers Flask.
      proxy: {
        '/api': { target: cibleApi, changeOrigin: true },
        '/uploads': { target: cibleApi, changeOrigin: true },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.js',
      css: false,
      // Les tests de formulaire saisissent au clavier champ par champ : 5 s (défaut) ne laisse
      // pas de marge sur une machine chargée (FRONT-004 : dépassements sans erreur d'assertion).
      testTimeout: 20000,
      // Heures affichées (« 21/10/2026 à 12:50 ») indépendantes du fuseau de la machine.
      env: { TZ: 'UTC' },
    },
  }
})
