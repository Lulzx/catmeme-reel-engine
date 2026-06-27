import { useEffect, useMemo, useState } from "react";
import { Input, Chip, Spinner } from "@heroui/react";
import { api, fmtDur, type MatchResult } from "../api";
import { IconWand, IconPlay, QualityChip, SectionTitle, usePlayer, Pill } from "../ui";

const SUGGESTIONS = [
  "screaming, rage",
  "sleepy, content",
  "smug, confident",
  "shocked, betrayed",
  "dancing, hype",
  "dead-inside, exhausted",
];

export function Match() {
  const [want, setWant] = useState("screaming, rage");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MatchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const play = usePlayer();

  useEffect(() => {
    const t = setTimeout(() => {
      if (!want.trim() && !query.trim()) {
        setResults([]);
        return;
      }
      setLoading(true);
      api
        .match(want, query)
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [want, query]);

  const maxScore = useMemo(
    () => Math.max(1, ...(results ?? []).map((r) => r.score)),
    [results],
  );

  return (
    <div>
      <SectionTitle
        title="Match playground"
        sub="See exactly which clip a feeling resolves to — the same scoring the renderer uses"
        icon={<IconWand className="w-5 h-5" />}
      />

      <div className="grid sm:grid-cols-2 gap-3 mb-3">
        <label className="block">
          <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5 block">
            Wanted emotions <span className="opacity-60">(comma-separated)</span>
          </span>
          <Input
            value={want}
            onChange={(e) => setWant(e.target.value)}
            placeholder="e.g. screaming, rage, outburst"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1.5 block">
            Free-text query <span className="opacity-60">(optional)</span>
          </span>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. boss losing his temper"
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 mb-7">
        <span className="text-xs text-zinc-400 mr-1">try:</span>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => {
              setWant(s);
              setQuery("");
            }}
            className="rounded-full bg-black/5 dark:bg-white/8 hover:bg-brand/20 text-zinc-600 dark:text-zinc-300 px-2.5 py-1 text-xs transition"
          >
            {s}
          </button>
        ))}
      </div>

      {results === null || loading ? (
        <div className="grid place-items-center py-20"><Spinner /></div>
      ) : results.length === 0 ? (
        <p className="text-center text-zinc-500 py-16">
          Type an emotion above to see matches.
        </p>
      ) : (
        <div className="space-y-2.5">
          {results.map((r, i) => (
            <Row
              key={r.id}
              r={r}
              rank={i + 1}
              pct={(r.score / maxScore) * 100}
              onPlay={() =>
                play({
                  src: r.clip,
                  title: r.primary,
                  subtitle: `#${r.id} · score ${r.score}`,
                  portrait: r.orientation === "portrait",
                })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Row({
  r,
  rank,
  pct,
  onPlay,
}: {
  r: MatchResult;
  rank: number;
  pct: number;
  onPlay: () => void;
}) {
  const top = rank === 1;
  return (
    <div
      className={
        "flex items-center gap-3 sm:gap-4 rounded-2xl border p-2.5 pr-3 sm:pr-4 transition " +
        (top
          ? "border-brand/50 bg-brand/8"
          : "border-black/5 dark:border-white/10 bg-white/50 dark:bg-white/[0.03]")
      }
    >
      <button
        onClick={onPlay}
        className="relative shrink-0 w-14 h-[72px] sm:w-16 sm:h-20 rounded-xl overflow-hidden bg-zinc-800 group"
      >
        <img src={r.frame} alt={r.primary} loading="lazy" className="w-full h-full object-cover" />
        <div className="absolute inset-0 grid place-items-center bg-black/30 opacity-0 group-hover:opacity-100 transition">
          <IconPlay className="w-6 h-6 text-white" />
        </div>
      </button>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-zinc-400">#{r.id}</span>
          <p className="font-medium text-zinc-900 dark:text-white truncate">{r.primary}</p>
          <QualityChip quality={r.quality} />
          {top && (
            <span className="hidden sm:inline-flex">
              <Chip size="sm" color="accent" variant="primary">
                best match
              </Chip>
            </span>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {r.matched.length > 0 ? (
            r.matched.map((m) => (
              <Chip key={m} size="sm" color="success" variant="soft">
                {m}
              </Chip>
            ))
          ) : (
            <span className="text-xs text-zinc-400">weak / fallback match</span>
          )}
          <Pill className="ml-1">{fmtDur(r.duration)}</Pill>
        </div>
      </div>

      <div className="shrink-0 w-14 sm:w-28 text-right">
        <div className="font-display font-bold text-lg text-zinc-900 dark:text-white tabular-nums">
          {r.score.toFixed(1)}
        </div>
        <div className="mt-1 h-1.5 rounded-full bg-black/10 dark:bg-white/10 overflow-hidden">
          <div
            className="h-full rounded-full bg-brand"
            style={{ width: `${Math.max(6, pct)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
