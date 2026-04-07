const backendUrl = process.env.BUN_PUBLIC_BACKEND_URL ?? "";

const result = await Bun.build({
  entrypoints: ["./src/index.html"],
  outdir: "./dist",
  sourcemap: "external",
  target: "browser",
  minify: true,
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
    __APP_BACKEND_URL__: JSON.stringify(backendUrl),
  },
});

if (!result.success) {
  for (const log of result.logs) {
    console.error(log);
  }
  process.exit(1);
}
