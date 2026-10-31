import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the app runs on :5173 and proxies the API, the stream and sign-in to the service on :8787,
// so cookies and relative URLs behave exactly as they do when the service serves the built files itself.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8787", changeOrigin: false, headers: { host: "127.0.0.1:8787" } },
      "/auth": { target: "http://127.0.0.1:8787", changeOrigin: false, headers: { host: "127.0.0.1:8787" } },
    },
  },
  build: { outDir: "dist", sourcemap: false },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
