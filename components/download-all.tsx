"use client";

import { useState } from "react";

/**
 * Starts every clip download in turn (hidden frames, a moment apart). The
 * browser may ask once whether to allow several downloads: say yes.
 */
export function DownloadOneByOne({ hrefs }: { hrefs: string[] }) {
  const [started, setStarted] = useState(0);
  const running = started > 0 && started < hrefs.length;

  function start() {
    hrefs.forEach((href, i) => {
      window.setTimeout(() => {
        const frame = document.createElement("iframe");
        frame.style.display = "none";
        frame.src = href;
        document.body.appendChild(frame);
        window.setTimeout(() => frame.remove(), 5 * 60 * 1000);
        setStarted(i + 1);
      }, i * 900);
    });
  }

  return (
    <button type="button" onClick={start} disabled={running} className="btn-quiet min-h-10 text-small disabled:opacity-60">
      {running ? `starting ${started} of ${hrefs.length}...` : started ? "downloads started" : "download one by one"}
    </button>
  );
}
