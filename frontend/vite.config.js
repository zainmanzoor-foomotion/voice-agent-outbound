import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the AI Call Agent dashboard.
// The dev server proxies /api/* to the FastAPI backend on :5000 so we
// avoid CORS preflight pain during local dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:5000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
