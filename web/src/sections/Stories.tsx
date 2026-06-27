import { useEffect, useRef, useState } from "react";
import { Button, Chip, Spinner } from "@heroui/react";
import {
  api,
  type StorySummary,
  type Story,
  type Beat,
  type CastMember,
} from "../api";
import {
  IconBook,
  IconBolt,
  IconPlay,
  IconFilm,
  QualityChip,
  SectionTitle,
  usePlayer,
  cn,
} from "../ui";

type LogLine = { line: string; kind?: string };

export function Stories() {
  const [list, setList] = useState<StorySummary[] | null>(null);
  const [slug, setSlug] = useState<string | null>(null);

  useEffect(() => {
    api.stories().then((s) => {
      setList(s);
      if (s.length) setSlug((cur) => cur ?? s[0].slug);
    });
  }, []);

  return (
    <div>
      <SectionTitle
        title="Stories"
        sub="Browse a narrative beat by beat, edit it, and render — live"
        icon={<IconBook className="w-5 h-5" />}
      />
      <div className="grid lg:grid-cols-[260px_1fr] gap-6">
        <aside className="space-y-2">
          {list === null ? (
            <Spinner />
          ) : (
            list.map((s) => (
              <button
                key={s.slug}
                onClick={() => setSlug(s.slug)}
                className={cn(
                  "w-full text-left rounded-xl border p-3 transition",
                  slug === s.slug
                    ? "border-brand/50 bg-brand/8"
                    : "border-black/5 dark:border-white/10 bg-white/50 dark:bg-white/[0.03] hover:border-brand/30",
                )}
              >
                <div className="font-medium text-sm text-zinc-900 dark:text-white">
                  {s.title}
                </div>
                <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                  {s.beats} beats · {s.slug}
                </div>
              </button>
            ))
          )}
        </aside>

        {slug ? <StoryDetail slug={slug} /> : <div />}
      </div>
    </div>
  );
}

function StoryDetail({ slug }: { slug: string }) {
  const [story, setStory] = useState<Story | null>(null);
  const [edit, setEdit] = useState(false);
  const [draft, setDraft] = useState("");
  const [saveMsg, setSaveMsg] = useState("");
  const [lines, setLines] = useState<LogLine[] | null>(null);
  const [rendering, setRendering] = useState(false);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);
  const play = usePlayer();

  useEffect(() => {
    setStory(null);
    setEdit(false);
    setLines(null);
    setResultUrl(null);
    api.story(slug).then((d) => {
      setStory(d.raw);
      setDraft(JSON.stringify(d.raw, null, 2));
    });
    return () => esRef.current?.close();
  }, [slug]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [lines]);

  function startRender() {
    setLines([]);
    setRendering(true);
    setResultUrl(null);
    const es = new EventSource(api.renderStreamUrl(slug));
    esRef.current = es;
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.done) {
        es.close();
        setRendering(false);
        if (data.ok && data.url) setResultUrl(data.url);
        setLines((l) => [
          ...(l ?? []),
          { line: data.ok ? "✓ render complete" : `✗ failed (code ${data.code})`, kind: "done" },
        ]);
      } else {
        setLines((l) => [...(l ?? []), { line: data.line, kind: data.kind }]);
      }
    };
    es.onerror = () => {
      es.close();
      setRendering(false);
      setLines((l) => [...(l ?? []), { line: "⚠ connection lost", kind: "err" }]);
    };
  }

  async function save() {
    try {
      const parsed = JSON.parse(draft) as Story;
      await api.saveStory(slug, parsed);
      setStory(parsed);
      setSaveMsg("saved ✓");
      setEdit(false);
    } catch (err) {
      setSaveMsg(`error: ${(err as Error).message}`);
    }
    setTimeout(() => setSaveMsg(""), 3000);
  }

  if (!story) return <div className="grid place-items-center py-24"><Spinner /></div>;

  return (
    <div className="min-w-0">
      {/* header card */}
      <div className="rounded-2xl border border-black/5 dark:border-white/10 bg-white/55 dark:bg-white/[0.03] p-5 mb-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-display text-xl font-semibold text-zinc-900 dark:text-white">
              {story.title ?? slug}
            </h3>
            {story.pov && <PovBubble text={story.pov} />}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant={edit ? "secondary" : "ghost"} onPress={() => setEdit((e) => !e)}>
              {edit ? "Close editor" : "Edit JSON"}
            </Button>
            <Button size="sm" variant="primary" isDisabled={rendering} onPress={startRender}>
              {rendering ? <Spinner size="sm" /> : <IconBolt className="w-4 h-4" />}
              {rendering ? "Rendering…" : "Render"}
            </Button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500 dark:text-zinc-400">
          <Chip size="sm" variant="soft" color="default">{story.beats.length} beats</Chip>
          {story.outro && <Chip size="sm" variant="soft" color="default">outro: {story.outro}</Chip>}
          <Chip size="sm" variant="soft" color="default">→ {story.output ?? "final.mp4"}</Chip>
        </div>
      </div>

      {/* json editor */}
      {edit && (
        <div className="rounded-2xl border border-black/5 dark:border-white/10 bg-white/55 dark:bg-white/[0.03] p-4 mb-5">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
            rows={18}
            className="tinybar w-full resize-y rounded-lg bg-zinc-50 dark:bg-black/40 border border-black/10 dark:border-white/10 p-3 font-mono text-xs text-zinc-800 dark:text-zinc-200 outline-none focus:border-brand/50"
          />
          <div className="mt-3 flex items-center gap-3">
            <Button size="sm" variant="primary" onPress={save}>Save story</Button>
            {saveMsg && (
              <span className={cn("text-xs", saveMsg.startsWith("error") ? "text-red-500" : "text-brand")}>
                {saveMsg}
              </span>
            )}
          </div>
        </div>
      )}

      {/* render console */}
      {lines !== null && (
        <div className="rounded-2xl border border-black/5 dark:border-white/10 bg-black/90 mb-5 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-white/10">
            <span className="text-xs font-mono text-zinc-400 flex items-center gap-2">
              <span className={cn("w-2 h-2 rounded-full", rendering ? "bg-brand animate-pulse" : "bg-zinc-600")} />
              render log
            </span>
            {resultUrl && (
              <Button
                size="sm"
                variant="primary"
                onPress={() => play({ src: resultUrl, title: story.title ?? slug, portrait: true })}
              >
                <IconPlay className="w-4 h-4" /> Watch result
              </Button>
            )}
          </div>
          <div ref={logRef} className="tinybar max-h-56 overflow-auto p-4 font-mono text-xs leading-relaxed">
            {lines.map((l, i) => (
              <div
                key={i}
                className={cn(
                  l.kind === "cmd" && "text-brand",
                  l.kind === "done" && "text-brand font-semibold",
                  l.kind === "err" && "text-red-400",
                  !l.kind && "text-zinc-300",
                )}
              >
                {l.line || " "}
              </div>
            ))}
            {rendering && <div className="text-zinc-500">▋</div>}
          </div>
        </div>
      )}

      {/* beats timeline */}
      <div className="space-y-3">
        {story.beats.map((b, i) => (
          <BeatRow key={i} beat={b} index={i} />
        ))}
      </div>
    </div>
  );
}

function PovBubble({ text }: { text: string }) {
  return (
    <div className="mt-2 inline-block max-w-xl">
      <span className="inline-block rounded-2xl bg-white text-zinc-900 font-semibold text-sm px-3.5 py-1.5 shadow-sm">
        {text}
      </span>
    </div>
  );
}

function BeatRow({ beat, index }: { beat: Beat; index: number }) {
  const scene = beat.bg?.place || beat.bg?.img || (beat.card ? "end card" : "—");
  return (
    <div className="flex gap-4 rounded-2xl border border-black/5 dark:border-white/10 bg-white/50 dark:bg-white/[0.03] p-4">
      <div className="shrink-0 grid place-items-center w-8 h-8 rounded-lg bg-black/5 dark:bg-white/8 font-display font-bold text-sm text-zinc-500 dark:text-zinc-400">
        {index + 1}
      </div>
      <div className="min-w-0 flex-1">
        {beat.card ? (
          <p className="font-display font-bold text-lg text-brand">🎬 {beat.card}</p>
        ) : (
          <p className="italic text-zinc-700 dark:text-zinc-200">{beat.action || "—"}</p>
        )}
        <p className="text-xs text-zinc-400 mt-1 flex items-center gap-1">
          <IconFilm className="w-3.5 h-3.5" /> scene: <span className="text-zinc-500 dark:text-zinc-300">{scene}</span>
        </p>
        <div className="mt-3 flex flex-wrap gap-3">
          {(beat.cast ?? []).map((c, j) => (
            <CastChip key={j} c={c} />
          ))}
          {(beat.cast ?? []).length === 0 && !beat.card && (
            <span className="text-xs text-zinc-400">no cast</span>
          )}
        </div>
      </div>
    </div>
  );
}

function CastChip({ c }: { c: CastMember }) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/5 dark:border-white/8 p-1.5 pr-3">
      {c.resolved ? (
        <img
          src={c.resolved.frame}
          alt={c.resolved.primary}
          loading="lazy"
          className="w-12 h-14 rounded-lg object-cover bg-zinc-800"
        />
      ) : (
        <div className="w-12 h-14 rounded-lg bg-zinc-200 dark:bg-zinc-800 grid place-items-center text-zinc-400">
          <IconFilm className="w-5 h-5" />
        </div>
      )}
      <div className="min-w-0">
        {c.name && (
          <div className="font-display font-bold text-xs tracking-wide text-zinc-900 dark:text-white uppercase">
            {c.name}
          </div>
        )}
        {c.resolved && (
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-xs text-zinc-500 dark:text-zinc-400 truncate max-w-[8rem]">
              {c.resolved.primary}
            </span>
            <QualityChip quality={c.resolved.quality} />
          </div>
        )}
        <div className="mt-1 flex flex-wrap gap-1 max-w-[12rem]">
          {(c.want ?? []).slice(0, 3).map((w) => (
            <span
              key={w}
              className="text-[10px] rounded bg-brand/15 text-brand px-1.5 py-0.5"
            >
              {w}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
