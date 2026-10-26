import { AppLink } from "@/components/nav/AppLink";
import { Box, Paper, Stack, Typography } from "@mui/material";

import { loadJson } from "@/lib/data";

type Digest = { date: string; title: string; sizeBytes: number };

export default async function DigestsPage() {
  const digests = await loadJson<Digest[]>("digests");

  return (
    <Box sx={{ maxWidth: 820, mx: "auto", px: { xs: 2, md: 3 }, py: 4 }}>
      <Typography variant="h1">Session digests</Typography>
      <Typography sx={{ color: "text.secondary", mt: 1, mb: 3 }}>
        What the system concluded on each research day, written in plain English and kept
        exactly as published — including the one that had to correct an earlier claim.
      </Typography>

      <Stack spacing={1}>
        {digests.map((d) => (
          <AppLink key={d.date} href={"/digests/" + d.date}>
            <Paper
              variant="outlined"
              sx={{ p: 2, "&:hover": { bgcolor: "action.hover" } }}
            >
            <Typography
              sx={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.78rem",
                color: "text.secondary",
              }}
            >
              {d.date}
            </Typography>
            <Typography sx={{ fontWeight: 600 }}>{d.title}</Typography>
            </Paper>
          </AppLink>
        ))}
      </Stack>
    </Box>
  );
}
