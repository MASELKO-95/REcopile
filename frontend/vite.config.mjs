import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from 'node:url';

export default defineConfig({
  resolve:{alias:{'@recopile/i18n':fileURLToPath(new URL('./src/i18n',import.meta.url))}},
  build: {
    outDir: "dist/client",
  },
  optimizeDeps: {
    include: ["react", "react-dom/client"],
  },
  server: {
    host: "127.0.0.1",
    allowedHosts: ["terminal.local"],
    proxy: { "/api": { target: "http://127.0.0.1:4783", changeOrigin: true } },
    warmup: {
      clientFiles: ["./src/main.jsx"],
    },
  },
  plugins: [react({jsxImportSource:'@recopile/i18n'})],
});
