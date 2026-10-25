"use client";

import { Box, Tooltip } from "@mui/material";

/**
 * How this app renders a number it does not have.
 *
 * An empty cell reads as zero. A bare dash reads as "nothing here". Both misrepresent data
 * the pipeline deliberately refused to invent, so absence gets a visible, hoverable marker
 * carrying the REASON — "this is a bank and banks file no gross profit", "the company
 * stopped reporting this tag in 2018", "total debt was suppressed because one component is
 * missing and summing the rest would understate it".
 *
 * This is the smallest component in the app and the one the product depends on most.
 */
export function UnavailableBadge({
  reason,
  compact = false,
}: {
  reason?: string;
  /** Shorter label for dense table cells. Keeps the marker and the tooltip — the point is
   *  that the cell is never blank, not that it is wordy. */
  compact?: boolean;
}) {
  return (
    <Tooltip
      title={reason ?? "Could not be computed from this company's filings"}
      arrow
      placement="top"
    >
      <Box
        component="span"
        sx={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.78rem",
          color: "text.disabled",
          borderBottom: "1px dotted",
          borderColor: "text.disabled",
          cursor: "help",
          whiteSpace: "nowrap",
        }}
      >
        {compact ? "n/a" : "not available"}
      </Box>
    </Tooltip>
  );
}
