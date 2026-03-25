import { defineConfig } from "vite";

export default defineConfig({
  publicDir: "output",
  define: {
    __BBOX__: JSON.stringify(process.env.BBOX || ""),
  },
});
