import type { Metadata } from "next";
import { Box, Typography } from "@mui/material";

import { TopNav } from "@/components/nav/TopNav";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "INVEST — research, with its uncertainty left in",
  description:
    "Equity research built on SEC filings, where an unmeasured figure says so instead of showing zero.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>
          <TopNav />
          <Box component="main">{children}</Box>
          <Box
            component="footer"
            sx={{
              borderTop: "1px solid",
              borderColor: "divider",
              mt: 6,
              py: 3,
              px: { xs: 2, md: 3 },
            }}
          >
            <Typography
              sx={{
                maxWidth: 1100,
                mx: "auto",
                fontSize: "0.72rem",
                color: "text.disabled",
              }}
            >
              Research and education only — not financial advice, and not the work of a
              licensed financial adviser. No return shown anywhere in this app is guaranteed.
              Fundamentals come from SEC EDGAR filings, prices from Yahoo Finance, macro series
              from FRED. Past predictions are kept exactly as they were written, including the
              wrong ones.
            </Typography>
          </Box>
        </Providers>
      </body>
    </html>
  );
}
