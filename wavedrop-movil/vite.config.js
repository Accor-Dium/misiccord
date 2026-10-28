import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// Tauri sirve la interfaz desde dist/ en producción y desde este servidor en desarrollo
export default defineConfig({
  plugins: [svelte()],
  clearScreen: false,
  server: { port: 1420, strictPort: true, host: process.env.TAURI_DEV_HOST || false },
  build: { target: "es2022", outDir: "dist", emptyOutDir: true },
});
