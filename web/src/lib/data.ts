import "server-only";

import { promises as fs } from "fs";
import path from "path";

/**
 * The only place this app reads data.
 *
 * It reads JSON files on disk, written by `python scripts/export_site_data.py` from the same
 * functions the FastAPI app serves. Nothing is fetched over the network at any point.
 *
 * WHY NOT CALL THE API
 *
 * The research record changes a few times a month, when a session runs. Serving that from a
 * live API meant a process that had to be hosted, paid for and kept awake, and a website that
 * broke whenever it wasn't. Reading frozen JSON means the whole site compiles to static HTML
 * that GitHub Pages hosts for free and that cannot fail at request time.
 *
 * The trade is explicit and worth stating on the page: **these figures are as of the last
 * export, not live market data.** That is already true of the underlying research - the
 * fundamentals come from quarterly filings - so a site that implied live prices would have
 * been lying about freshness it never had.
 *
 * The API in `api/` is still the source of this data and is still useful locally
 * (`http://localhost:8000/docs`). It is just no longer on the critical path for the website.
 */

const DATA_DIR = path.join(process.cwd(), "public", "data");

export class MissingData extends Error {
  readonly name = "MissingData";
  constructor(readonly file: string) {
    super(
      `No data file "${file}.json". Run: python scripts/export_site_data.py`,
    );
  }
}

/** Load one exported file, or throw MissingData. */
export async function loadJson<T>(file: string): Promise<T> {
  try {
    const raw = await fs.readFile(path.join(DATA_DIR, file + ".json"), "utf8");
    return JSON.parse(raw) as T;
  } catch {
    throw new MissingData(file);
  }
}

/**
 * Load one exported file, or null if it isn't there.
 *
 * Used where absence is a real state rather than a failure — a company that has been
 * analysed but never scored has no thesis file, and that page should render without one
 * instead of 500ing.
 */
export async function loadJsonOrNull<T>(file: string): Promise<T | null> {
  try {
    return await loadJson<T>(file);
  } catch {
    return null;
  }
}

export type Manifest = {
  generatedAt: string;
  companies: string[];
  digests: string[];
  counts: { companies: number; digests: number; files: number };
  note: string;
};

/** When the data on this site was last refreshed. Shown in the footer. */
export async function generatedAt(): Promise<string | null> {
  const m = await loadJsonOrNull<Manifest>("manifest");
  return m?.generatedAt ?? null;
}
