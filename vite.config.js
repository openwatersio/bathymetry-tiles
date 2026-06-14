import { defineConfig } from "vite";

export default defineConfig({
  publicDir: "output",
  define: {
    __BBOX__: JSON.stringify(process.env.BBOX || ""),
    // Base URL tiles are served from. Empty = relative (local dev serves from
    // output/ via publicDir); production sets it to the R2 host.
    __TILES_BASE__: JSON.stringify(process.env.TILES_BASE || ""),
  },
});
