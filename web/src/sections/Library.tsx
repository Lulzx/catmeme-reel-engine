import { useEffect, useMemo, useState } from "react";
import { Input, Spinner, Chip } from "@heroui/react";
import { api, fmtDur, type Clip } from "../api";
import {
  IconGrid,
  IconSearch,
  IconPlay,
  QualityChip,
  SectionTitle,
  usePlayer,
  cn,
} from "../ui";

const QUALITIES: Clip["quality"][] = ["good", "ok", "partial", "low", "avoid"];

export function Library() {
  const [clips, setClips] = useState<Clip[] | null>(null);
  const [q, setQ] = useState("");
  const [quality, setQuality] = useState<Clip["quality"] | "all">("all");
  const play = usePlayer();

  useEffect(() => {
    api.catalog().then(setClips).catch(() => setClips([]));
  }, []);

  const filtered = useMemo(() => {
    if (!clips) return [];
    const needle = q.trim().toLowerCase();
    return clips.filter((c) => {
      if (quality !== "all" && c.quality !== quality) return false;
      if (!needle) return true;
      return (
        c.primary.toLowerCase().includes(needle) ||
        c.use_for.toLowerCase().includes(needle) ||
        c.emotions.some((e) => e.includes(needle)) ||
        c.id === needle
      );
    });
  }, [clips, q, quality]);

  return (
    <div>
      <SectionTitle
        title="Clip library"
        sub={`${clips?.length ?? "…"} green-screen clips, each described once`}
        icon={<IconGrid className="w-5 h-5" />}
      />

      {/* controls */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1 max-w-md">
          <IconSearch className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search feeling, action, tag, or id…"
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <FilterPill active={quality === "all"} onClick={() => setQuality("all")}>
            all
          </FilterPill>
          {QUALITIES.map((qq) => (
            <FilterPill key={qq} active={quality === qq} onClick={() => setQuality(qq)}>
              {qq}
            </FilterPill>
          ))}
        </div>
      </div>

      {clips === null ? (
        <div className="grid place-items-center py-24"><Spinner /></div>
      ) : filtered.length === 0 ? (
        <p className="text-center text-zinc-500 py-20">No clips match that filter.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-4">
          {filtered.map((c) => (
            <ClipCard
              key={c.id}
              c={c}
              onPlay={() =>
                play({
                  src: c.clip,
                  title: c.primary,
                  subtitle: `#${c.id} · ${c.sound}`,
                  portrait: c.orientation === "portrait",
                })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterPill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full px-3 py-1.5 text-xs font-medium capitalize transition",
        active
          ? "bg-brand text-black"
          : "bg-black/5 dark:bg-white/8 text-zinc-600 dark:text-zinc-300 hover:bg-black/10 dark:hover:bg-white/12",
      )}
    >
      {children}
    </button>
  );
}

function ClipCard({ c, onPlay }: { c: Clip; onPlay: () => void }) {
  return (
    <div className="group rounded-2xl overflow-hidden border border-black/5 dark:border-white/10 bg-white/60 dark:bg-white/5 hover:border-brand/40 transition shadow-sm">
      <button onClick={onPlay} className="relative block w-full aspect-[4/5] bg-zinc-800 overflow-hidden">
        <img
          src={c.frame}
          alt={c.primary}
          loading="lazy"
          className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-80" />
        <div className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100 transition">
          <div className="grid place-items-center w-12 h-12 rounded-full bg-brand/90 text-black">
            <IconPlay className="w-5 h-5 translate-x-0.5" />
          </div>
        </div>
        <span className="absolute top-2 left-2 rounded bg-black/65 text-white/90 text-[10px] font-mono px-1.5 py-0.5">
          #{c.id}
        </span>
        <span className="absolute bottom-2 right-2 rounded bg-black/65 text-white/90 text-[10px] px-1.5 py-0.5">
          {fmtDur(c.duration)}
        </span>
      </button>
      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <p className="font-medium text-sm text-zinc-900 dark:text-white leading-tight">
            {c.primary}
          </p>
          <QualityChip quality={c.quality} />
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {c.emotions.slice(0, 3).map((e) => (
            <Chip key={e} size="sm" variant="soft" color="default">
              {e}
            </Chip>
          ))}
        </div>
      </div>
    </div>
  );
}
