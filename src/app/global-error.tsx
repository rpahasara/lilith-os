"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";
import { reportProblem } from "@/lib/diagnostics";

/**
 * The last line of defence: an error in the root layout or the shell itself.
 * It replaces the whole document, so it carries its own <html> and <body> and
 * its own minimal styling — the app stylesheet is not available here.
 */
export default function GlobalError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    reportProblem("shell", "the application shell failed to render", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          display: "grid",
          placeItems: "center",
          background: "#080609",
          color: "#f3eef4",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <title>Lilith OS — something went wrong</title>
        <main style={{ maxWidth: 420, padding: 28, textAlign: "center" }}>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Lilith OS could not start</h1>
          <p style={{ margin: "12px 0 20px", fontSize: 14, lineHeight: 1.6, color: "#bcb1c1" }}>
            Something went wrong before the interface could be drawn. Nothing was changed.
          </p>
          <button
            type="button"
            onClick={() => retry()}
            style={{
              cursor: "pointer",
              borderRadius: 999,
              border: "1px solid rgba(201,84,115,0.5)",
              background: "rgba(129,42,73,0.5)",
              color: "#f3eef4",
              padding: "9px 18px",
              fontSize: 13,
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
