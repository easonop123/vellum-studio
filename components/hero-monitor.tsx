"use client";

import { useEffect, useRef, useState } from "react";
import { timecode } from "@/lib/site";

/**
 * The hero "program monitor": the demo plays muted on loop with a live
 * timecode and REC light burned in, like the edits themselves.
 */
export function HeroMonitor({ src, poster, label }: { src: string; poster: string; label: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const tcRef = useRef<HTMLSpanElement>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    // The label follows the video itself, so autoplay being blocked shows up too.
    const onPlay = () => setPaused(false);
    const onPause = () => setPaused(true);
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) video.pause();
    else video.play().catch(onPause);
    let raf = 0;
    const tick = () => {
      if (tcRef.current) tcRef.current.textContent = timecode(video.currentTime);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
    };
  }, []);

  function toggle() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) video.play().catch(() => setPaused(true));
    else video.pause();
  }

  return (
    <div className="absolute inset-0 overflow-hidden bg-graphite lg:rounded-[3px]">
      <video
        ref={videoRef}
        className="h-full w-full object-cover"
        src={src}
        poster={poster}
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        aria-label={`demo edit: ${label}`}
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center gap-2 bg-gradient-to-b from-ink/70 to-transparent px-4 pt-3 pb-8 text-label text-bone mono lg:px-3.5">
        <span className={paused ? "inline-block size-[0.62em] rounded-full bg-ash" : "rec-dot"} aria-hidden />
        <span>{paused ? "PAUSED" : "REC"}</span>
        <span ref={tcRef} className="text-bone/80">
          00:00:00:00
        </span>
      </div>
      <button
        type="button"
        onClick={toggle}
        className="absolute top-2 right-2 rounded-[3px] px-2.5 py-1.5 text-label text-bone/85 mono hover:bg-ink/50 hover:text-bone"
      >
        {paused ? "play" : "pause"}
      </button>
    </div>
  );
}
