import { useEffect, useRef, useState } from "react";
import { Button, Chip, Spinner } from "@heroui/react";
import {
  api,
  type SagaSummary,
  type Saga,
  type SagaScene,
  type SagaCast,
} from "../api";
import {
  IconScroll,
  IconBolt,
  IconPlay,
  IconFilm,
  SectionTitle,
  usePlayer,
  cn,
} from "../ui";

type LogLine = { line: string; kind?: string };

export function Sagas() {
  const [list, setList] = useState<SagaSummary[] | null>(null);
  const [slug, setSlug] = useState<string | null>(null);

  useEffect(() => {
    api.sagas().then((s) => {
      setList(s);
      if (s.length) setSlug((cur) => cur ?? s[0].slug);
    });
  }, []);

  return (
    <div>
      <SectionTitle
        title="Sagas"
        sub="Long-form narrated cat stories — build narration + render locally, then schedule"
        icon={<IconScroll className="w-5 h-5" />}
      />
      <div className="grid lg:grid-cols-[260px_1fr] gap-5 lg:gap-6">
        <aside className="flex lg:flex-col gap-2 overflow-x-auto lg:overflow-visible -mx-4 px-4 pb-2 lg:mx-0 lg:px-0 lg:pb-0 tinybar snap-x">
          {list === null ? (
            <Spinner />
          ) : list.length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400 px-1">
              No sagas yet. Author one as <code>data/sagas/&lt;slug&gt;.json</code>.
            </p>
          ) : (
            list.map((s) => (
              <button
                key={s.slug}
                onClick={() => setSlug(s.slug)}
                className={cn(
                  "shrink-0 w-56 lg:w-full snap-start text-left rounded-xl border p-3 transition",
                  slug === s.slug
                    ? "border-brand/50 bg-brand/8"
                    : "border-black/5 dark:border-white/10 bg-white/50 dark:bg-white/[0.03] hover:border-brand/30",
                )}
              >
                <div className="font-medium text-sm text-zinc-900 dark:text-white">
                  {s.title}
                </div>
                <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                  {s.scenes} scenes · {s.narrator || s.slug}
                </div>
              </button>
            ))
          )}
        </aside>

        {slug ? <SagaDetail key={slug} slug={slug} /> : <div />}
      </div>
    </div>
  );
}

function SagaDetail({ slug }: { slug: string }) {
  const [saga, setSaga] = useState<Saga | null>(null);
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
    setSaga(null);
    setEdit(false);
    setLines(null);
    setResultUrl(null);
    api.saga(slug).then((d) => {
      setSaga(d.raw);
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
    const es = new EventSource(api.sagaRenderStreamUrl(slug));
    esRef.current = es;
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.done) {
        es.close();
        setRendering(false);
        if (data.ok && data.url) setResultUrl(data.url);
        setLines((l) => [
          ...(l ?? []),
          {
            line: data.ok ? "✓ built, rendered & queued" : `✗ failed (code ${data.code})`,
            kind: data.ok ? "done" : "err",
          },
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
      const parsed = JSON.parse(draft) as Saga;
      await api.saveSaga(slug, parsed);
      setSaga(parsed);
      setSaveMsg("saved ✓");
      setEdit(false);
    } catch (err) {
      setSaveMsg(`error: ${(err as Error).message}`);
    }
    setTimeout(() => setSaveMsg(""), 3000);
  }

  if (!saga) return <div className="grid place-items-center py-24"><Spinner /></div>;

  const cv = saga.canvas;
  const scenes = saga.scenes ?? [];

  return (
    <div className="min-w-0">
      {/* header card */}
      <div className="rounded-2xl border border-black/5 dark:border-white/10 bg-white/55 dark:bg-white/[0.03] p-5 mb-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-display text-xl font-semibold text-zinc-900 dark:text-white">
              {saga.title ?? slug}
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              narrated long-form · renders on this Mac, $0
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant={edit ? "secondary" : "ghost"} onPress={() => setEdit((e) => !e)}>
              {edit ? "Close editor" : "Edit JSON"}
            </Button>
            <Button size="sm" variant="primary" isDisabled={rendering} onPress={startRender}>
              {rendering ? <Spinner size="sm" /> : <IconBolt className="w-4 h-4" />}
              {rendering ? "Building…" : "Build & Render"}
            </Button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500 dark:text-zinc-400">
          <Chip size="sm" variant="soft" color="default">{scenes.length} scenes</Chip>
          {saga.voice?.narrator && (
            <Chip size="sm" variant="soft" color="default">🎙 {saga.voice.narrator}</Chip>
          )}
          {cv && <Chip size="sm" variant="soft" color="default">{cv.w}×{cv.h} @{cv.fps}</Chip>}
          <Chip size="sm" variant="soft" color="default">→ {saga.output ?? `${slug}.mp4`}</Chip>
        </div>
      </div>

      {/* json editor */}
      {edit && (
        <div className="rounded-2xl border border-black/5 dark:border-white/10 bg-white/55 dark:bg-white/[0.03] p-4 mb-5">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
            rows={20}
            className="tinybar w-full resize-y rounded-lg bg-zinc-50 dark:bg-black/40 border border-black/10 dark:border-white/10 p-3 font-mono text-xs text-zinc-800 dark:text-zinc-200 outline-none focus:border-brand/50"
          />
          <div className="mt-3 flex items-center gap-3">
            <Button size="sm" variant="primary" onPress={save}>Save saga</Button>
            {saveMsg && (
              <span className={cn("text-xs", saveMsg.startsWith("error") ? "text-red-500" : "text-brand")}>
                {saveMsg}
              </span>
            )}
          </div>
        </div>
      )}

      {/* build/render console */}
      {lines !== null && (
        <div className="rounded-2xl border border-black/5 dark:border-white/10 bg-black/90 mb-5 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-white/10">
            <span className="text-xs font-mono text-zinc-400 flex items-center gap-2">
              <span className={cn("w-2 h-2 rounded-full", rendering ? "bg-brand animate-pulse" : "bg-zinc-600")} />
              build + render log
            </span>
            {resultUrl && (
              <Button
                size="sm"
                variant="primary"
                onPress={() => play({ src: resultUrl, title: saga.title ?? slug })}
              >
                <IconPlay className="w-4 h-4" /> Watch result
              </Button>
            )}
          </div>
          <div ref={logRef} className="tinybar max-h-64 overflow-auto p-4 font-mono text-xs leading-relaxed">
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
                {l.line || " "}
              </div>
            ))}
            {rendering && <div className="text-zinc-500">▋</div>}
          </div>
        </div>
      )}

      {/* scene timeline */}
      <div className="space-y-3">
        {scenes.map((sc, i) => (
          <SceneRow key={sc.id ?? i} scene={sc} index={i} />
        ))}
      </div>
    </div>
  );
}

function castArray(cast: SagaScene["cast"]): SagaCast[] {
  if (!cast) return [];
  return Array.isArray(cast) ? cast : [cast];
}

function SceneRow({ scene, index }: { scene: SagaScene; index: number }) {
  const isTransform = scene.kind === "transformation";
  const bg = scene.bg?.img || scene.bg?.place || (isTransform ? "split-screen" : "—");
  return (
    <div className="flex gap-4 rounded-2xl border border-black/5 dark:border-white/10 bg-white/50 dark:bg-white/[0.03] p-4">
      <div className="shrink-0 grid place-items-center w-8 h-8 rounded-lg bg-black/5 dark:bg-white/8 font-display font-bold text-sm text-zinc-500 dark:text-zinc-400">
        {index + 1}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          {scene.mood && (
            <span className="text-[10px] uppercase tracking-wide rounded bg-brand/15 text-brand px-1.5 py-0.5">
              {scene.mood}
            </span>
          )}
          {isTransform && (
            <span className="text-[10px] uppercase tracking-wide rounded bg-fuchsia-500/20 text-fuchsia-400 px-1.5 py-0.5">
              transformation
            </span>
          )}
          <span className="text-xs text-zinc-400 flex items-center gap-1">
            <IconFilm className="w-3.5 h-3.5" />
            <span className="text-zinc-500 dark:text-zinc-300">{bg}</span>
          </span>
        </div>

        {scene.vo && (
          <p className="italic text-zinc-700 dark:text-zinc-200 mt-2 leading-snug">
            “{scene.vo}”
          </p>
        )}
        {scene.caption && (
          <p className="text-xs text-zinc-400 mt-1">caption: {scene.caption}</p>
        )}

        <div className="mt-3 flex flex-wrap gap-2">
          {isTransform
            ? (scene.panels ?? []).map((p, j) => (
                <span
                  key={j}
                  className="text-xs rounded-lg bg-black/[0.03] dark:bg-white/[0.04] border border-black/5 dark:border-white/8 px-2.5 py-1.5"
                >
                  <b className="text-zinc-700 dark:text-zinc-200">{p.label ?? `panel ${j + 1}`}</b>
                  <span className="text-zinc-400"> · {p.bg?.img ?? p.mood ?? ""}</span>
                </span>
              ))
            : castArray(scene.cast).map((c, j) => <CastChip key={j} c={c} />)}
        </div>
      </div>
    </div>
  );
}

function CastChip({ c }: { c: SagaCast }) {
  return (
    <div className="flex items-center gap-2 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/5 dark:border-white/8 px-2.5 py-1.5">
      {c.name && (
        <span className="font-display font-bold text-[11px] tracking-wide text-zinc-900 dark:text-white uppercase">
          {c.name}
        </span>
      )}
      {c.clip ? (
        <span className="text-xs text-zinc-500 dark:text-zinc-300">clip #{c.clip}</span>
      ) : (
        <div className="flex flex-wrap gap-1 max-w-[14rem]">
          {(c.want ?? []).slice(0, 4).map((w) => (
            <span key={w} className="text-[10px] rounded bg-brand/15 text-brand px-1.5 py-0.5">
              {w}
            </span>
          ))}
          {(c.want ?? []).length === 0 && (
            <span className="text-xs text-zinc-400">auto-match</span>
          )}
        </div>
      )}
    </div>
  );
}
