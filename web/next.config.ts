import type { NextConfig } from "next";

/**
 * Built as a static site: `next build` emits plain HTML/CSS/JS into `out/`, with no Node
 * server at request time. GitHub Pages hosts that for free and it cannot fall over.
 *
 * This works because every page reads JSON written ahead of time by
 * `python scripts/export_site_data.py`, so there is nothing left to compute per request.
 *
 * BASE PATH: a GitHub Pages *project* site is served from a subfolder —
 * https://cm0407.github.io/AI-Investment-Project/ — so every asset and link needs that
 * prefix or the page loads with no styles. The workflow sets NEXT_PUBLIC_BASE_PATH; locally
 * it is empty so http://localhost:3000 still works.
 */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  assetPrefix: basePath || undefined,
  // Pages has no image optimiser (that needs a server), so images ship as-is.
  images: { unoptimized: true },
  // Emits each route as a folder with an index.html, which is what a plain file host wants.
  trailingSlash: true,
};

export default nextConfig;
