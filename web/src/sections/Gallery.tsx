import { useEffect, useState } from "react";
import { Button, Spinner } from "@heroui/react";
import { api, fmtBytes, fmtDur, timeAgo, type Output } from "../api";
import { IconFilm, IconPlay, usePlayer, cn } from "../ui";

export function Gallery({ onAuthor }: { onAuthor: () => void }) {
  const [outputs, setOutputs] = useState<Output[] | null>(null);
  const play = usePlayer();

  useEffect(() => {
    api.outputs().then(setOutputs).catch(() => setOutputs([]));
  }, []);

  const totalSecs = outputs?.reduce((a, o) => a + o.duration, 0) ?? 0;

  return (
    <div>
      {/* hero */}
      <div className="relative overflow-hidden rounded-3xl border border-black/5 dark:border-white/10 bg-gradient-to-br from-white/60 to-white/20 dark:from-white/5 dark:to-transparent p-8 sm:p-10 mb-8">
        <div className="absolute -right-16 -top-16 w-64 h-64 rounded-full bg-brand/20 blur-3xl" />
        <div className="relative max-w-2xl">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-brand/15 text-brand px-3 py-1 text-xs font-semibold mb-4">
            <IconFilm className="w-3.5 h-3.5" /> Rendered reels
          </span>
          <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight text-zinc-900 dark:text-white">
            Your cat-meme gallery
          </h1>
          <p className="mt-3 text-zinc-600 dark:text-zinc-300">
            Every finished POV reel, ready to play. Write a story and render a new
            one — clips are matched, grounded, labelled and stitched automatically.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button variant="primary" onPress={onAuthor}>
              <IconFilm className="w-4 h-4" /> Author a story
            </Button>
            <div className="flex items-center gap-5 text-sm text-zinc-500 dark:text-zinc-400">
              <Stat n={outputs?.length ?? 0} label="reels" />
              <Stat n={Math.round(totalSecs)} label="seconds" />
            </div>
          </div>
        </div>
      </div>

      {outputs === null ? (
        <div className="grid place-items-center py-24"><Spinner /></div>
      ) : outputs.length === 0 ? (
        <Empty onAuthor={onAuthor} />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-5">
          {outputs.map((o) => (
            <ReelCard
              key={o.name}
              o={o}
              onPlay={() =>
                play({ src: o.url, title: o.name, subtitle: fmtDur(o.duration), portrait: true })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <span>
      <span className="font-display font-bold text-zinc-900 dark:text-white text-lg">{n}</span>{" "}
      {label}
    </span>
  );
}

function ReelCard({ o, onPlay }: { o: Output; onPlay: () => void }) {
  return (
    <button
      onClick={onPlay}
      className="group text-left rounded-2xl overflow-hidden border border-black/5 dark:border-white/10 bg-black/90 ring-0 hover:ring-2 hover:ring-brand/60 transition shadow-sm hover:shadow-xl"
    >
      <div className="relative aspect-[9/16] bg-zinc-900">
        {o.poster ? (
          <img
            src={o.poster}
            alt={o.name}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-[1.03] transition duration-500"
          />
        ) : (
          <div className="w-full h-full grid place-items-center text-white/30">
            <IconFilm className="w-10 h-10" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent" />
        <div className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100 transition">
          <div className="grid place-items-center w-14 h-14 rounded-full bg-brand text-black shadow-lg scale-90 group-hover:scale-100 transition">
            <IconPlay className="w-6 h-6 translate-x-0.5" />
          </div>
        </div>
        <span className="absolute top-2 right-2 rounded-md bg-black/70 text-white text-[11px] font-medium px-1.5 py-0.5 backdrop-blur">
          {fmtDur(o.duration)}
        </span>
      </div>
      <div className="p-3">
        <p className="font-medium text-sm text-zinc-900 dark:text-white truncate">
          {o.name.replace(/\.(mp4|mov|webm)$/, "")}
        </p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
          {fmtBytes(o.size)} · {timeAgo(o.mtime)}
        </p>
      </div>
    </button>
  );
}

function Empty({ onAuthor }: { onAuthor: () => void }) {
  return (
    <div className={cn("grid place-items-center py-24 text-center")}>
      <div className="grid place-items-center w-16 h-16 rounded-2xl bg-brand/15 text-brand mb-4">
        <IconFilm className="w-8 h-8" />
      </div>
      <h3 className="font-display text-xl font-semibold text-zinc-900 dark:text-white">
        No reels yet
      </h3>
      <p className="text-zinc-500 dark:text-zinc-400 mt-1 mb-5 max-w-sm">
        Head to Stories, pick a narrative and hit render. It lands here when it's done.
      </p>
      <Button variant="primary" onPress={onAuthor}>Go to Stories</Button>
    </div>
  );
}
