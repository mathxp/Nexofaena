import { readFileSync, existsSync } from "fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Certificado autofirmado para probar la cámara del kiosco (reconocimiento
// facial) en un dispositivo real por IP de LAN: los navegadores bloquean
// getUserMedia en cualquier origen que no sea "seguro" (HTTPS o localhost).
// Generado con: openssl req -x509 -nodes -newkey rsa:2048 ... (ver .certs/san.cnf).
// Si no existe, Vite simplemente sirve por HTTP normal (dev en localhost sigue andando).
const certKeyPath = "./.certs/kiosco-dev-key.pem";
const certPath = "./.certs/kiosco-dev-cert.pem";
const httpsConfig =
  existsSync(certKeyPath) && existsSync(certPath)
    ? { key: readFileSync(certKeyPath), cert: readFileSync(certPath) }
    : undefined;

// La misma config de https+proxy sirve para "npm run dev" (desarrollo, con
// HMR) y "npm run preview" (sirve el build de producción ya optimizado) —
// preview es lo que corresponde dejar corriendo de forma sostenida, porque
// el modo dev manda módulos sin bundlear/minificar (más lento para cargar
// el chunk pesado de face-api.js) y hace trabajo extra pensado para
// desarrollo activo, no para dejarlo prendido todo el turno.
const servidorConfig = {
  host: "0.0.0.0",
  // Puerto fijo también en "preview" (que por defecto usa 4173): así la
  // URL que quede guardada en el navegador del kiosco/dispositivos no
  // cambia según si detrás está corriendo dev o preview.
  port: 5173,
  https: httpsConfig,
  proxy: {
    // El navegador le habla a Vite (HTTPS, mismo origen que la página),
    // y Vite reenvía servidor-a-servidor a Django (HTTP, sin TLS) — así
    // el backend no necesita certificado propio ni CORS especial, y no
    // hay contenido mixto (HTTPS llamando a HTTP) que el navegador bloquee.
    "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
  },
};

export default defineConfig({
  server: servidorConfig,
  preview: servidorConfig,
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "apple-touch-icon.png", "masked-icon.svg"],
      manifest: {
        name: "NexoFaena SGI",
        short_name: "NexoFaena",
        description: "Sistema de Gestión de Inventario NexoFaena",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        start_url: "/",
        icons: [
          {
            src: "/pwa-192x192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/pwa-512x512.png",
            sizes: "512x512",
            type: "image/png",
          },
        ],
      },
      workbox: {
        // Los pesos de face-api.js (kiosco de reconocimiento facial) no
        // tienen extensión reconocida por el glob por defecto ni caben en
        // el límite de 5MB (face_recognition_model-shard1 pesa ~4.2MB) —
        // sin esto, el service worker nunca los precachea y el kiosco
        // queda sin reconocimiento facial en modo offline.
        globPatterns: ["**/*.{js,css,html,ico,png,svg,webmanifest}", "models/**/*"],
        maximumFileSizeToCacheInBytes: 8 * 1024 * 1024,
      },
    }),
  ],
});
