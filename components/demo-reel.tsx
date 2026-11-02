"use client";

import { useEffect, useRef, useState } from "react";

type Demo = { title: string; video: string; poster: string; clips: number; seconds: number };

const SOUND_EVENT = "vellum:sound-on";

function DemoClip({ demo, index }: { demo: Demo; index: number }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [visible, setVisible] = useState(false);
  const [soundOn, setSoundOn] = useState(false);

  // Play only while mostly on screen; nothing loads until then.
  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.intersectionRatio >= 0.6) {
          setVisible(true);
          if (!reduce) video.play().catch(() => undefined);
        } else {
          video.pause();
        }
      },
      { threshold: [0, 0.6, 1] },
    );
    observer.observe(video);
    return () => observer.disconnect();
  }, []);

  // Only one demo plays sound at a time.
  useEffect(() => {
    const onOther = (e: Event) => {
      if ((e as CustomEvent<number>).detail !== index) setSoundOn(false);
    };
    window.addEventListener(SOUND_EVENT, onOther);
    return () => window.removeEventListener(SOUND_EVENT, onOther);
  }, [index]);

  useEffect(() => {
    if (ref.current) ref.current.muted = !soundOn;
  }, [soundOn]);

  function toggleSound() {
    const next = !soundOn;
    setSoundOn(next);
    if (next) {
      window.dispatchEvent(new CustomEvent(SOUND_EVENT, { detail: index }));
      ref.current?.play().catch(() => undefined);
    }
  }

  return (
    <figure className="w-[72vw] max-w-[19rem] shrink-0 snap-start sm:w-auto sm:max-w-none">
      <div className="relative aspect-[9/16] overflow-hidden rounded-[3px] bg-graphite">
        <video
          ref={ref}
          className="h-full w-full object-cover"
          src={visible ? demo.video : undefined}
          poster={demo.poster}
          muted
          loop
          playsInline
          preload="none"
          aria-label={`demo edit: ${demo.title}`}
        />
        <button
          type="button"
          onClick={toggleSound}
          aria-pressed={soundOn}
          className="absolute right-2 bottom-2 rounded-[3px] bg-ink/70 px-2.5 py-1.5 text-label text-bone mono backdrop-blur hover:bg-ink"
        >
          {soundOn ? "sound on" : "sound off"}
        </button>
      </div>
      <figcaption className="mt-3 flex items-baseline justify-between gap-3">
        <span className="display text-h3">{demo.title}</span>
        <span className="text-label text-ash mono">
          {demo.clips} clips → {demo.seconds} s
        </span>
      </figcaption>
    </figure>
  );
}

export function DemoReel({ demos }: { demos: Demo[] }) {
  return (
    <div className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 [scrollbar-width:none] sm:mx-0 sm:grid sm:grid-cols-3 sm:gap-6 sm:overflow-visible sm:px-0">
      {demos.map((demo, i) => (
        <DemoClip key={demo.title} demo={demo} index={i} />
      ))}
    </div>
  );
}
