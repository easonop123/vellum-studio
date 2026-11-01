"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { timecode } from "@/lib/site";

/**
 * Before/after wipe. The raw clip sits underneath, the edit on top, and a
 * safelight playhead (like an editing timeline's) splits them. Drag it, or
 * focus it and use the arrow keys.
 */
export function RawEditWipe({
  raw,
  edit,
  poster,
  rawLabel,
}: {
  raw: string;
  edit: string;
  poster: string;
  rawLabel: string;
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const rawRef = useRef<HTMLVideoElement>(null);
  const editRef = useRef<HTMLVideoElement>(null);
  const tcRef = useRef<HTMLSpanElement>(null);
  const dragging = useRef(false);
  const [pos, setPos] = useState(50);
  const [active, setActive] = useState(false);

  // Only load and play while it's on screen.
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const observer = new IntersectionObserver(
      ([entry]) => {
        const videos = [rawRef.current, editRef.current].filter(Boolean) as HTMLVideoElement[];
        if (entry.isIntersecting) {
          setActive(true);
          if (!reduce) videos.forEach((v) => v.play().catch(() => undefined));
        } else {
          videos.forEach((v) => v.pause());
        }
      },
      { rootMargin: "200px 0px" },
    );
    observer.observe(frame);
    return () => observer.disconnect();
  }, []);

  // Keep the two clips in step and run the timecode.
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const e = editRef.current;
      const r = rawRef.current;
      if (e && r && !e.paused && Math.abs(r.currentTime - e.currentTime) > 0.08) r.currentTime = e.currentTime;
      if (e && tcRef.current) tcRef.current.textContent = timecode(e.currentTime);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const moveTo = useCallback((clientX: number) => {
    const frame = frameRef.current;
    if (!frame) return;
    const rect = frame.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setPos(Math.min(100, Math.max(0, pct)));
  }, []);

  return (
    <div className="w-full">
      <div
        ref={frameRef}
        className="relative aspect-[4/5] w-full touch-pan-y select-none overflow-hidden rounded-[3px] bg-graphite"
        onPointerDown={(e) => {
          dragging.current = true;
          e.currentTarget.setPointerCapture(e.pointerId);
          moveTo(e.clientX);
        }}
        onPointerMove={(e) => {
          if (dragging.current) moveTo(e.clientX);
        }}
        onPointerUp={() => {
          dragging.current = false;
        }}
        onPointerCancel={() => {
          dragging.current = false;
        }}
      >
        <video
          ref={rawRef}
          className="absolute inset-0 h-full w-full object-cover"
          src={active ? raw : undefined}
          poster={poster}
          muted
          loop
          playsInline
          preload="none"
          aria-hidden
        />
        <video
          ref={editRef}
          className="absolute inset-0 h-full w-full object-cover"
          style={{ clipPath: `inset(0 0 0 ${pos}%)` }}
          src={active ? edit : undefined}
          poster={poster}
          muted
          loop
          playsInline
          preload="none"
          aria-label="before and after: the raw clip on the left, my edit on the right"
        />

        {/* playhead: drag anywhere on the frame, or focus the handle and use the arrow keys */}
        <div className="pointer-events-none absolute inset-y-0 w-0" style={{ left: `${pos}%` }}>
          <div className="absolute inset-y-0 -left-px w-0.5 bg-safelight" aria-hidden />
          <div
            className="absolute top-0 -left-[9px] h-4 w-[18px] bg-safelight [clip-path:polygon(0_0,100%_0,100%_55%,50%_100%,0_55%)]"
            aria-hidden
          />
          <div
            role="slider"
            tabIndex={0}
            aria-label="move the line between the raw clip and the edit"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(pos)}
            aria-valuetext={`${Math.round(pos)}% raw`}
            onKeyDown={(e) => {
              const step = e.shiftKey ? 20 : 5;
              const keys: Record<string, number> = {
                ArrowLeft: pos - step,
                ArrowDown: pos - step,
                ArrowRight: pos + step,
                ArrowUp: pos + step,
                Home: 0,
                End: 100,
              };
              if (e.key in keys) {
                e.preventDefault();
                setPos(Math.min(100, Math.max(0, keys[e.key])));
              }
            }}
            className="pointer-events-auto absolute bottom-6 -left-[22px] grid size-11 cursor-ew-resize place-items-center rounded-full bg-safelight text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-bone"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
              <path d="M6 3 2 8l4 5M10 3l4 5-4 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>

        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 bg-gradient-to-t from-ink/80 to-transparent px-3 pt-10 pb-3 text-label mono">
          <span className="text-bone/90">{rawLabel}</span>
          <span className="flex items-center gap-1.5 text-bone">
            <span className="rec-dot" aria-hidden />
            <span ref={tcRef}>00:00:00:00</span>
          </span>
        </div>
      </div>

    </div>
  );
}
