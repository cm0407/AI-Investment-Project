import { Box, Typography } from "@mui/material";

/**
 * A deliberately tiny Markdown renderer for the daily digests.
 *
 * The digests are written by this system in a known, narrow subset — headings, bullets,
 * bold, horizontal rules — so a full Markdown library (and its HTML-injection surface)
 * would be more risk and weight than the job needs.
 */
function inline(text: string, key: number) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return (
    <span key={key}>
      {parts.map((p, i) => {
        if (p.startsWith("**") && p.endsWith("**")) {
          return <strong key={i}>{p.slice(2, -2)}</strong>;
        }
        if (p.startsWith("`") && p.endsWith("`")) {
          return (
            <Box
              key={i}
              component="code"
              sx={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.85em",
                bgcolor: "action.hover",
                px: 0.5,
                borderRadius: 0.5,
              }}
            >
              {p.slice(1, -1)}
            </Box>
          );
        }
        return <span key={i}>{p}</span>;
      })}
    </span>
  );
}

export function Markdown({ source }: { source: string }) {
  const lines = source.split("\n");

  return (
    <Box sx={{ "& > *": { mb: 1.25 } }}>
      {lines.map((raw, i) => {
        const line = raw.trimEnd();

        if (!line.trim()) return <Box key={i} sx={{ height: 4 }} />;

        if (/^---+$/.test(line.trim())) {
          return (
            <Box
              key={i}
              sx={{ borderTop: "1px solid", borderColor: "divider", my: 2.5 }}
            />
          );
        }

        const heading = /^(#{1,4})\s+(.*)$/.exec(line);
        if (heading) {
          const level = heading[1].length;
          return (
            <Typography
              key={i}
              variant={level === 1 ? "h2" : level === 2 ? "h3" : "subtitle2"}
              sx={{ mt: level <= 2 ? 3 : 2 }}
            >
              {inline(heading[2], i)}
            </Typography>
          );
        }

        const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
        if (bullet) {
          return (
            <Box key={i} sx={{ display: "flex", gap: 1.25, pl: 1 }}>
              <Box sx={{ color: "text.disabled" }}>•</Box>
              <Typography variant="body2">{inline(bullet[1], i)}</Typography>
            </Box>
          );
        }

        return (
          <Typography key={i} variant="body2">
            {inline(line, i)}
          </Typography>
        );
      })}
    </Box>
  );
}
