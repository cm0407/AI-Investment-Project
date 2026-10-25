"use client";

import NextLink from "next/link";
import { Box } from "@mui/material";
import type { SxProps, Theme } from "@mui/material/styles";

/**
 * The app's only link primitive.
 *
 * It exists because of an App Router rule rather than a design preference: MUI components
 * are Client Components, so a Server Component cannot hand one `component={Link}` — React
 * refuses to serialise a function across that boundary and the build fails on it. Doing the
 * composition once, here, behind a `"use client"` marker keeps every page a Server Component
 * (so API calls and the base URL stay on the server) and keeps exactly one client bundle
 * for navigation.
 */
export function AppLink({
  href,
  sx,
  children,
}: {
  href: string;
  sx?: SxProps<Theme>;
  children: React.ReactNode;
}) {
  return (
    <Box
      component={NextLink}
      href={href}
      sx={[
        { textDecoration: "none", color: "inherit", display: "block" },
        ...(Array.isArray(sx) ? sx : [sx]),
      ]}
    >
      {children}
    </Box>
  );
}
