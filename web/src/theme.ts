"use client";

import { createTheme } from "@mui/material/styles";

/**
 * Single source of truth for every visual decision. Use `sx` referencing these tokens —
 * never `style={{}}`, never a hardcoded hex.
 *
 * IDENTITY: an instrument panel, not a brokerage app.
 *
 * Brokerage apps are designed to make trading feel good. This one has to make UNCERTAINTY
 * legible, which pulls in the opposite direction — toward restraint, tabular figures, and
 * colour used sparingly enough that when it does appear it means something.
 *
 * THE COLOUR RULE, which everything else follows from:
 *   success/error are reserved for REALISED outcomes measured against something — a price
 *   move versus its entry, a return versus the index. Scores, quality judgements and
 *   projections get neutral treatment. A 79 is not "good"; it is 79, and the reasoning
 *   behind it is a click away.
 */
export const theme = createTheme({
  cssVariables: { colorSchemeSelector: "class" },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: "#1b4965" },        // slate blue — reads as instrument, not brand
        success: { main: "#1b7f3b" },
        error: { main: "#b3261e" },
        warning: { main: "#8a5a00" },
        background: { default: "#fbfbfa", paper: "#ffffff" },
        divider: "#e3e6e8",
        text: { primary: "#16202a", secondary: "#5a6672", disabled: "#97a1ab" },
      },
    },
    dark: {
      palette: {
        primary: { main: "#7fb3d5" },
        success: { main: "#5bbd7a" },
        error: { main: "#e8705f" },
        warning: { main: "#d9a441" },
        background: { default: "#0f1419", paper: "#161c23" },
        divider: "#262e37",
        text: { primary: "#e8edf2", secondary: "#9aa7b4", disabled: "#636f7c" },
      },
    },
  },
  typography: {
    fontFamily: "var(--font-inter), system-ui, sans-serif",
    // Every number in this app uses the mono stack with tabular figures. Proportional
    // digits make columns of financials jitter, which is unreadable at a glance.
    h1: { fontSize: "1.9rem", fontWeight: 600, letterSpacing: "-0.015em" },
    h2: { fontSize: "1.45rem", fontWeight: 600, letterSpacing: "-0.01em" },
    h3: { fontSize: "1.15rem", fontWeight: 600 },
    subtitle2: {
      fontSize: "0.78rem",
      fontWeight: 600,
      letterSpacing: "0.05em",
      textTransform: "uppercase",
    },
    body2: { fontSize: "0.875rem" },
  },
  shape: { borderRadius: 6 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { textTransform: "none", boxShadow: "none" },
      },
      defaultProps: { disableElevation: true },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          fontVariantNumeric: "tabular-nums",
          paddingTop: 8,
          paddingBottom: 8,
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: { fontSize: "0.78rem", maxWidth: 360, lineHeight: 1.5 },
      },
    },
  },
});
