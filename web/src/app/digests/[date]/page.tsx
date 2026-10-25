import { AppLink } from "@/components/nav/AppLink";
import { Box, Paper, Typography } from "@mui/material";

import { Markdown } from "@/components/markdown/Markdown";
import { fetchInvestApi } from "@/lib/api";

export const dynamic = "force-dynamic";

type Digest = { date: string; markdown: string };

export default async function DigestPage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const digest = await fetchInvestApi<Digest>("/digests/" + date);

  return (
    <Box sx={{ maxWidth: 780, mx: "auto", px: { xs: 2, md: 3 }, py: 4 }}>
      <AppLink href="/digests" sx={{ display: "inline-block" }}>
        <Typography sx={{ fontSize: "0.8rem", color: "text.secondary" }}>
          ← all digests
        </Typography>
      </AppLink>

      <Paper variant="outlined" sx={{ p: { xs: 2, md: 3.5 }, mt: 2 }}>
        <Markdown source={digest.markdown} />
      </Paper>

      <Typography sx={{ mt: 2, fontSize: "0.72rem", color: "text.disabled" }}>
        Published {digest.date} and kept unedited. Where a later session found an error in this
        one, the correction appears in a later digest rather than being patched into this one.
      </Typography>
    </Box>
  );
}
