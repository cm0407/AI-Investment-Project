import { Box, Stack, Typography } from "@mui/material";

import { AppLink } from "@/components/nav/AppLink";

const LINKS = [
  { href: "/predictions", label: "Predictions" },
  { href: "/screen", label: "Screen" },
  { href: "/macro", label: "Macro" },
  { href: "/digests", label: "Digests" },
];

export function TopNav() {
  return (
    <Box
      component="header"
      sx={{
        borderBottom: "1px solid",
        borderColor: "divider",
        bgcolor: "background.paper",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      <Box
        sx={{
          maxWidth: 1100,
          mx: "auto",
          px: { xs: 2, md: 3 },
          py: 1.5,
          display: "flex",
          alignItems: "baseline",
          gap: 3,
          flexWrap: "wrap",
        }}
      >
        <AppLink href="/" sx={{ display: "inline-block" }}>
          <Typography
            sx={{ fontWeight: 700, letterSpacing: "0.12em", fontSize: "0.9rem" }}
          >
            INVEST
          </Typography>
        </AppLink>

        <Stack direction="row" sx={{ gap: 2.5, flexWrap: "wrap" }}>
          {LINKS.map((l) => (
            <AppLink key={l.href} href={l.href} sx={{ display: "inline-block" }}>
              <Typography
                sx={{
                  fontSize: "0.85rem",
                  color: "text.secondary",
                  "&:hover": { color: "text.primary" },
                }}
              >
                {l.label}
              </Typography>
            </AppLink>
          ))}
        </Stack>
      </Box>
    </Box>
  );
}
