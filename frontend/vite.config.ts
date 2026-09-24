import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// During development, /api is proxied to the FastAPI backend so no CORS setup is needed.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Leaflet + Recharts make a ~1 MB bundle; fine for a single-page dashboard served locally.
  build: { chunkSizeWarningLimit: 1200 },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
});
