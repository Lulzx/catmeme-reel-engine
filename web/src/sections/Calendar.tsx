import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Button, Spinner } from "@heroui/react";
import { api, type Schedule, type ScheduleVideo, type VideoStatus, type VideoStats } from "../api";
import {
  SectionTitle,
  usePlayer,
  cn,
  IconCalendar,
  IconClock,
  IconChevronLeft,
  IconChevronRight,
  IconYoutube,
  IconPlay,
  IconCheck,
  IconCat,
  IconExternal,
  IconEye,
  IconHeart,
  IconWand,
  IconClose,
} from "../ui";

/* ---------------------------------------------------------------- helpers -- */
const STATUS: Record<VideoStatus, { label: string; dot: string; chip: string; ring: string }> = {
  posted:    { label: "Live",      dot: "bg-emerald-500", chip: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400", ring: "ring-emerald-500/40" },
  scheduled: { label: "Scheduled", dot: "bg-sky-500",     chip: "bg-sky-500/15 text-sky-600 dark:text-sky-400",             ring: "ring-sky-500/40" },
  queued:    { label: "Queued",    dot: "bg-amber-500",   chip: "bg-amber-500/15 text-amber-600 dark:text-amber-400",       ring: "ring-amber-500/40" },
  authored:  { label: "Draft",     dot: "bg-zinc-400",    chip: "bg-zinc-500/15 text-zinc-500 dark:text-zinc-400",          ring: "ring-zinc-400/40" },
};
const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DOW = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

function whenOf(v: ScheduleVideo): Date | null {
  if (v.publish_at) return new Date(v.publish_at);
  if (v.posted) { const [y, m, d] = v.posted.split("-").map(Number); return new Date(y, m - 1, d); }
  return null;
}
const dayKey = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
const sameDay = (a: Date, b: Date) => dayKey(a) === dayKey(b);
const cleanTitle = (v: ScheduleVideo) => v.pov.replace(/^POV:\s*/i, "");
const timeLabel = (d: Date) => d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const fmtNum = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : `${n}`);

function fmtCountdown(ms: number): string {
  if (ms <= 0) return "now";
  const s = Math.floor(ms / 1000), d = Math.floor(s / 86400),
    h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

/* lanes = setting / background scene (from backgrounds/<name>) */
const SCENES: Record<string, string> = {
  airport: "✈️ Airport", amusementpark: "🎡 Amusement Park", bank: "🏦 Bank",
  beach: "🏖️ Beach", cinema: "🎬 Cinema", classroom: "🏫 Classroom",
  concert: "🎤 Concert", fantacy: "🪄 Fantasy", forest: "🌲 Forest",
  grassland: "🌿 Grassland", gym: "🏋️ Gym", highway: "🛣️ Highway", home: "🏠 Home",
  hospital: "🏥 Hospital", kitchen: "🍳 Kitchen", lab: "🧪 Lab", library: "📚 Library",
  mountain: "⛰️ Mountain", museum: "🖼️ Museum", office: "💼 Office", park: "🌳 Park",
  playground: "🛝 Playground", pool: "🏊 Pool", port: "⚓ Port", restaurant: "🍽️ Restaurant",
  river: "🏞️ River", rooftop: "🌆 Rooftop", school: "🎒 School", shop: "🛍️ Shop",
  stage: "🎭 Stage", station: "🚉 Station", theater: "🎟️ Theater", village: "🏡 Village",
  others: "📍 Other",
};
const sceneLabel = (id: string) => SCENES[id] ?? id.charAt(0).toUpperCase() + id.slice(1);
const laneOf = (v: ScheduleVideo): string => v.place ?? "other";

/* ------------------------------------------------------------------ view --- */
export function Calendar() {
  const [data, setData] = useState<Schedule | null>(null);
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [now, setNow] = useState(() => Date.now());
  const [lane, setLane] = useState("all");
  const [stats, setStats] = useState<Record<string, VideoStats>>({});
  const [statsErr, setStatsErr] = useState<string | null>(null);
  const [gen, setGen] = useState(false);
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const play = usePlayer();

  useEffect(() => { api.schedule().then(setData).catch(() => setData({ channel: {}, defaults: {}, videos: [] })); }, []);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(t); }, []);
  useEffect(() => {
    api.analytics().then((r) => { if (r.error) setStatsErr(r.error); else setStats(r.stats ?? {}); }).catch(() => {});
  }, []);

  const allVideos = data?.videos ?? [];
  const lanesPresent = useMemo(() => {
    const ids = [...new Set(allVideos.map(laneOf))].filter((x) => x !== "other").sort();
    return ids.map((id) => ({ id, label: sceneLabel(id) }));
  }, [allVideos]);
  const videos = useMemo(
    () => (lane === "all" ? allVideos : allVideos.filter((v) => laneOf(v) === lane)),
    [allVideos, lane],
  );
  const counts = useMemo(() => {
    const c: Record<string, number> = { posted: 0, scheduled: 0, queued: 0, authored: 0 };
    for (const v of allVideos) c[v.status] = (c[v.status] ?? 0) + 1;
    return c;
  }, [allVideos]);

  const nextUp = useMemo(() => {
    return allVideos
      .filter((v) => v.status === "scheduled" && v.publish_at && new Date(v.publish_at).getTime() > now)
      .sort((a, b) => new Date(a.publish_at!).getTime() - new Date(b.publish_at!).getTime())[0] ?? null;
  }, [allVideos, now]);

  const totalViews = useMemo(() => Object.values(stats).reduce((a, s) => a + s.views, 0), [stats]);
  const topPerformers = useMemo(() => {
    return allVideos
      .filter((v) => v.video_id && stats[v.video_id]?.views)
      .sort((a, b) => stats[b.video_id!].views - stats[a.video_id!].views)
      .slice(0, 3);
  }, [allVideos, stats]);

  const byDay = useMemo(() => {
    const m = new Map<string, ScheduleVideo[]>();
    for (const v of videos) { const d = whenOf(v); if (!d) continue; const k = dayKey(d); (m.get(k) ?? m.set(k, []).get(k)!).push(v); }
    for (const arr of m.values()) arr.sort((a, b) => (whenOf(a)!.getTime()) - (whenOf(b)!.getTime()));
    return m;
  }, [videos]);

  const agenda = useMemo(() => {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const rows = videos
      .map((v) => ({ v, d: whenOf(v) }))
      .filter((r): r is { v: ScheduleVideo; d: Date } => !!r.d && r.d.getTime() >= today.getTime())
      .sort((a, b) => a.d.getTime() - b.d.getTime());
    const groups: { key: string; date: Date; items: ScheduleVideo[] }[] = [];
    for (const { v, d } of rows) {
      const k = dayKey(d);
      let g = groups.find((x) => x.key === k);
      if (!g) { g = { key: k, date: d, items: [] }; groups.push(g); }
      g.items.push(v);
    }
    return groups;
  }, [videos]);

  const openVideo = (v: ScheduleVideo) => {
    if (v.output_url) play({ src: v.output_url, title: cleanTitle(v), subtitle: STATUS[v.status].label, portrait: true });
    else if (v.youtube_url) window.open(v.youtube_url, "_blank");
  };

  const refresh = () => api.schedule().then(setData).catch(() => {});
  const onReschedule = async (slug: string, day: Date) => {
    const v = allVideos.find((x) => x.slug === slug);
    if (!v || !v.publish_at) return;
    const o = new Date(v.publish_at);
    const nd = new Date(day.getFullYear(), day.getMonth(), day.getDate(), o.getHours(), o.getMinutes(), o.getSeconds());
    if (sameDay(nd, o)) return;
    if (nd.getTime() <= Date.now()) { alert("Drop onto a future day to reschedule."); return; }
    try { await api.reschedule(slug, nd.toISOString()); await refresh(); }
    catch (e) { alert("Reschedule failed: " + ((e as Error).message || e)); }
  };

  if (!data) return <div className="grid place-items-center py-24"><Spinner /></div>;

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <SectionTitle
          title="Content calendar"
          sub="Every reel — live, scheduled and queued — on one timeline."
          icon={<IconCalendar className="w-5 h-5" />}
        />
        <Button variant="primary" onPress={() => setGen((g) => !g)} className="shrink-0">
          <IconWand className="w-4 h-4" /> Generate
        </Button>
      </div>

      {gen && <GeneratePanel onClose={() => setGen(false)} onDone={refresh} />}

      {statsErr === "reauth" && (
        <div className="mb-5 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-300 flex items-center gap-2">
          <IconEye className="w-4 h-4 shrink-0" />
          <span>Connect analytics to see views &amp; likes — run <code className="font-mono text-xs">python3 -m engine.upload --auth</code> once to grant read access.</span>
        </div>
      )}

      {/* dashboard row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <NextUpCard v={nextUp} now={now} onOpen={openVideo} channel={data.channel} />
        <StatCard label="Live" value={counts.posted} accent="emerald" icon={<IconCheck className="w-4 h-4" />}
          sub={totalViews > 0 ? `${fmtNum(totalViews)} total views` : undefined} />
        <StatCard label="Scheduled" value={counts.scheduled} accent="sky" icon={<IconClock className="w-4 h-4" />} />
        <StatCard label="In queue" value={counts.queued + counts.authored} accent="amber" icon={<IconCalendar className="w-4 h-4" />} />
      </div>

      {topPerformers.length > 0 && (
        <div className="mb-8">
          <div className="text-xs font-semibold uppercase tracking-wide text-zinc-400 mb-2">Top performers</div>
          <div className="grid gap-2.5 sm:grid-cols-3">
            {topPerformers.map((v) => (
              <button key={v.slug} onClick={() => openVideo(v)} className="group flex items-center gap-3 rounded-2xl border border-black/5 dark:border-white/10 bg-white/50 dark:bg-white/[0.03] p-2.5 text-left hover:ring-2 hover:ring-brand/40 transition">
                <div className="relative shrink-0 w-10 h-[58px] rounded-lg overflow-hidden bg-zinc-900 grid place-items-center">
                  {v.poster ? <img src={v.poster} alt="" className="w-full h-full object-cover" /> : <IconCat className="w-4 h-4 text-white/30" />}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-900 dark:text-white truncate">{cleanTitle(v)}</p>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                    <span className="inline-flex items-center gap-1"><IconEye className="w-3.5 h-3.5" />{fmtNum(stats[v.video_id!].views)}</span>
                    <span className="inline-flex items-center gap-1"><IconHeart className="w-3.5 h-3.5" />{fmtNum(stats[v.video_id!].likes)}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* lane filter */}
      {lanesPresent.length > 1 && (
        <div className="flex flex-wrap items-center gap-1.5 mb-5">
          <FilterChip active={lane === "all"} onClick={() => setLane("all")}>All lanes</FilterChip>
          {lanesPresent.map((l) => (
            <FilterChip key={l.id} active={lane === l.id} onClick={() => setLane(l.id)}>{l.label}</FilterChip>
          ))}
        </div>
      )}

      {/* month calendar */}
      <div className="rounded-3xl border border-black/5 dark:border-white/10 bg-white/50 dark:bg-white/[0.03] p-4 sm:p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display text-xl font-semibold text-zinc-900 dark:text-white">
            {MONTHS[month.getMonth()]} {month.getFullYear()}
          </h3>
          <div className="flex items-center gap-1.5">
            <Button size="sm" variant="ghost" onPress={() => { const d = new Date(); setMonth(new Date(d.getFullYear(), d.getMonth(), 1)); }}>Today</Button>
            <button onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))} className="grid place-items-center w-8 h-8 rounded-lg text-zinc-500 hover:bg-black/5 dark:hover:bg-white/5 transition" aria-label="Previous month"><IconChevronLeft className="w-5 h-5" /></button>
            <button onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))} className="grid place-items-center w-8 h-8 rounded-lg text-zinc-500 hover:bg-black/5 dark:hover:bg-white/5 transition" aria-label="Next month"><IconChevronRight className="w-5 h-5" /></button>
          </div>
        </div>
        <MonthGrid
          month={month}
          byDay={byDay}
          today={now}
          selectedKey={selectedDay ? dayKey(selectedDay) : null}
          onOpenDay={setSelectedDay}
          onReschedule={onReschedule}
        />
        <Legend />
      </div>

      <DayDetail
        day={selectedDay}
        byDay={byDay}
        stats={stats}
        now={now}
        onClose={() => setSelectedDay(null)}
        onNav={(delta) => setSelectedDay((d) => (d ? new Date(d.getFullYear(), d.getMonth(), d.getDate() + delta) : d))}
        onOpen={openVideo}
        onGenerate={() => { setSelectedDay(null); setGen(true); }}
      />

      {/* agenda */}
      <SectionTitle title="Upcoming" sub="What goes out next, grouped by day." icon={<IconClock className="w-5 h-5" />} />
      {agenda.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-black/10 dark:border-white/10 p-10 text-center text-zinc-500 dark:text-zinc-400">
          Nothing scheduled ahead. Render more reels and run <code className="text-brand">--fill-schedule</code> to extend the calendar.
        </div>
      ) : (
        <div className="space-y-6">
          {agenda.map((g) => (
            <div key={g.key}>
              <div className="flex items-center gap-2 mb-2">
                <span className="font-display font-semibold text-zinc-900 dark:text-white">{DOW[g.date.getDay()]}</span>
                <span className="text-sm text-zinc-500 dark:text-zinc-400">{MONTHS[g.date.getMonth()].slice(0, 3)} {g.date.getDate()}</span>
                <span className="text-xs text-zinc-400">· {g.items.length} {g.items.length === 1 ? "reel" : "reels"}</span>
              </div>
              <div className="grid gap-2.5">
                {g.items.map((v) => <AgendaRow key={v.slug} v={v} now={now} onOpen={openVideo} stats={v.video_id ? stats[v.video_id] : undefined} />)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- subviews -- */
function NextUpCard({ v, now, onOpen, channel }: { v: ScheduleVideo | null; now: number; onOpen: (v: ScheduleVideo) => void; channel: Schedule["channel"] }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-black/5 dark:border-white/10 bg-gradient-to-br from-brand/15 to-transparent p-4 lg:col-span-1">
      <div className="absolute -right-10 -top-10 w-32 h-32 rounded-full bg-brand/20 blur-3xl" />
      <div className="relative">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-brand">Next up</span>
          {channel.url && (
            <a href={channel.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition">
              <IconCat className="w-3.5 h-3.5" /> {channel.name ?? "channel"} <IconExternal className="w-3 h-3" />
            </a>
          )}
        </div>
        {v ? (
          <button onClick={() => onOpen(v)} className="mt-2 text-left w-full group">
            <p className="font-display font-semibold text-zinc-900 dark:text-white leading-snug line-clamp-2 group-hover:text-brand transition">{cleanTitle(v)}</p>
            <div className="mt-2 flex items-center gap-1.5 text-sm">
              <IconClock className="w-4 h-4 text-brand" />
              <span className="font-semibold text-zinc-900 dark:text-white">in {fmtCountdown(new Date(v.publish_at!).getTime() - now)}</span>
              <span className="text-zinc-400">· {timeLabel(new Date(v.publish_at!))}</span>
            </div>
          </button>
        ) : (
          <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">Nothing scheduled — queue is clear.</p>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, accent, icon, sub }: { label: string; value: number; accent: "emerald" | "sky" | "amber"; icon: React.ReactNode; sub?: string }) {
  const a = { emerald: "text-emerald-500 bg-emerald-500/10", sky: "text-sky-500 bg-sky-500/10", amber: "text-amber-500 bg-amber-500/10" }[accent];
  return (
    <div className="rounded-2xl border border-black/5 dark:border-white/10 bg-white/50 dark:bg-white/[0.03] p-4 flex items-center gap-3">
      <div className={cn("grid place-items-center w-10 h-10 rounded-xl", a)}>{icon}</div>
      <div className="min-w-0">
        <div className="font-display text-2xl font-bold text-zinc-900 dark:text-white leading-none">{value}</div>
        <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 truncate">{sub ?? label}</div>
      </div>
    </div>
  );
}

function MonthGrid({ month, byDay, today, selectedKey, onOpenDay, onReschedule }: {
  month: Date; byDay: Map<string, ScheduleVideo[]>; today: number; selectedKey: string | null;
  onOpenDay: (day: Date) => void; onReschedule: (slug: string, day: Date) => void;
}) {
  const [over, setOver] = useState<string | null>(null);
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const lead = first.getDay();
  const cells: (Date | null)[] = [];
  for (let i = 0; i < lead; i++) cells.push(null);
  for (let d = 1; d <= days; d++) cells.push(new Date(month.getFullYear(), month.getMonth(), d));
  while (cells.length % 7 !== 0) cells.push(null);
  const todayStart = new Date(today); todayStart.setHours(0, 0, 0, 0);
  const todayKey = dayKey(new Date(today));

  return (
    <div>
      <div className="grid grid-cols-7 gap-1 sm:gap-1.5 mb-1.5">
        {DOW.map((d) => (
          <div key={d} className="text-center text-[10px] sm:text-[11px] font-semibold text-zinc-400 uppercase tracking-wide py-1">
            <span className="sm:hidden">{d[0]}</span>
            <span className="hidden sm:inline">{d}</span>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
        {cells.map((d, i) => {
          if (!d) return <div key={i} className="rounded-xl bg-transparent" />;
          const key = dayKey(d);
          const items = byDay.get(key) ?? [];
          const isToday = key === todayKey;
          const isSelected = key === selectedKey;
          const isOver = over === key;
          const isWeekend = d.getDay() === 0 || d.getDay() === 6;
          const past = d.getTime() < todayStart.getTime();
          // status summary for the cell's top accent bar
          const seg = { posted: 0, scheduled: 0, queued: 0, authored: 0 } as Record<VideoStatus, number>;
          for (const v of items) seg[v.status]++;
          return (
            <button
              key={i}
              type="button"
              onClick={() => onOpenDay(d)}
              onDragOver={(e) => { if (!past) { e.preventDefault(); setOver(key); } }}
              onDragLeave={() => setOver((o) => (o === key ? null : o))}
              onDrop={(e) => { e.preventDefault(); setOver(null); const slug = e.dataTransfer.getData("text/plain"); if (slug && !past) onReschedule(slug, d); }}
              className={cn(
                "group relative flex flex-col text-left min-h-[56px] sm:min-h-[96px] rounded-lg sm:rounded-xl border p-1 sm:p-1.5 transition outline-none",
                "hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/5 dark:hover:shadow-black/40 focus-visible:ring-2 focus-visible:ring-brand/60",
                isOver ? "border-brand ring-2 ring-brand/50 bg-brand/10"
                  : isSelected ? "border-brand ring-2 ring-brand/40 bg-brand/[0.07]"
                  : isToday ? "border-brand/50 bg-brand/[0.06] hover:border-brand/70"
                  : cn("border-black/5 dark:border-white/[0.06] hover:border-black/10 dark:hover:border-white/15",
                      isWeekend ? "bg-black/[0.025] dark:bg-white/[0.015]" : "bg-black/[0.015] dark:bg-white/[0.02]"),
                past && "opacity-65 hover:opacity-100",
              )}
            >
              {/* status accent bar */}
              {items.length > 0 && (
                <div className="absolute inset-x-1.5 top-0 flex h-[3px] gap-px overflow-hidden rounded-b-sm">
                  {(["posted", "scheduled", "queued", "authored"] as VideoStatus[]).map((k) =>
                    seg[k] ? <span key={k} className={cn("h-full", STATUS[k].dot)} style={{ flex: seg[k] }} /> : null,
                  )}
                </div>
              )}
              <div className="flex items-center justify-between mb-1 pt-0.5">
                <span className={cn(
                  "grid place-items-center text-[11px] font-bold tabular-nums leading-none",
                  isToday ? "w-5 h-5 rounded-full bg-brand text-black" : "px-0.5 text-zinc-400 dark:text-zinc-500",
                )}>{d.getDate()}</span>
                {items.length > 0 && (
                  <span className="text-[10px] font-semibold text-zinc-400 dark:text-zinc-500 tabular-nums">{items.length}</span>
                )}
              </div>
              {/* mobile: a compact dot row — cells are too narrow for titles */}
              {items.length > 0 && (
                <div className="flex sm:hidden flex-wrap gap-1 mt-auto pt-0.5">
                  {items.slice(0, 8).map((v) => (
                    <span key={v.slug} className={cn("w-1.5 h-1.5 rounded-full", STATUS[v.status].dot)} />
                  ))}
                </div>
              )}
              <div className="hidden sm:block space-y-1">
                {items.slice(0, 3).map((v) => {
                  const s = STATUS[v.status];
                  const drag = v.status === "scheduled";
                  return (
                    <div key={v.slug} title={drag ? `${cleanTitle(v)} — drag to reschedule` : cleanTitle(v)}
                      draggable={drag}
                      onClick={(e) => { e.stopPropagation(); onOpenDay(d); }}
                      onDragStart={(e) => { e.dataTransfer.setData("text/plain", v.slug); e.dataTransfer.effectAllowed = "move"; }}
                      className={cn("flex items-center gap-1 rounded-md pl-1 pr-1 py-0.5 text-[10px] leading-tight transition hover:ring-1", drag && "cursor-grab active:cursor-grabbing", s.chip, s.ring)}>
                      {v.poster
                        ? <img src={v.poster} alt="" loading="lazy" className="shrink-0 w-3 h-[18px] rounded-[3px] object-cover bg-zinc-900" />
                        : <span className={cn("shrink-0 w-1.5 h-1.5 rounded-full", s.dot)} />}
                      <span className="truncate">{cleanTitle(v)}</span>
                    </div>
                  );
                })}
                {items.length > 3 && (
                  <div className="text-[10px] font-medium text-zinc-400 dark:text-zinc-500 px-1 group-hover:text-brand transition">+{items.length - 3} more</div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- day detail --- */
function DayDetail({ day, byDay, stats, now, onClose, onNav, onOpen, onGenerate }: {
  day: Date | null; byDay: Map<string, ScheduleVideo[]>; stats: Record<string, VideoStats>;
  now: number; onClose: () => void; onNav: (delta: number) => void;
  onOpen: (v: ScheduleVideo) => void; onGenerate: () => void;
}) {
  useEffect(() => {
    if (!day) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") onNav(-1);
      if (e.key === "ArrowRight") onNav(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [day, onClose, onNav]);

  const items = day ? byDay.get(dayKey(day)) ?? [] : [];
  const isToday = day ? sameDay(day, new Date(now)) : false;
  const seg = { posted: 0, scheduled: 0, queued: 0, authored: 0 } as Record<VideoStatus, number>;
  for (const v of items) seg[v.status]++;

  return (
    <AnimatePresence>
      {day && (
        <motion.div
          className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-sm"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="relative flex h-full w-full sm:max-w-md flex-col border-l border-black/10 dark:border-white/10 bg-white/85 dark:bg-ink/85 backdrop-blur-2xl shadow-2xl"
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 360, damping: 36 }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* header */}
            <div className="shrink-0 border-b border-black/5 dark:border-white/10 p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-display text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
                      {DOW[day.getDay()]}, {MONTHS[day.getMonth()].slice(0, 3)} {day.getDate()}
                    </span>
                    {isToday && <span className="rounded-full bg-brand px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-black">Today</span>}
                  </div>
                  <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                    {items.length === 0 ? "No reels scheduled" : `${items.length} ${items.length === 1 ? "reel" : "reels"}`}
                    {seg.posted > 0 && ` · ${seg.posted} live`}
                    {seg.scheduled > 0 && ` · ${seg.scheduled} scheduled`}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => onNav(-1)} className="grid place-items-center w-8 h-8 rounded-lg text-zinc-500 hover:bg-black/5 dark:hover:bg-white/5 transition" aria-label="Previous day"><IconChevronLeft className="w-5 h-5" /></button>
                  <button onClick={() => onNav(1)} className="grid place-items-center w-8 h-8 rounded-lg text-zinc-500 hover:bg-black/5 dark:hover:bg-white/5 transition" aria-label="Next day"><IconChevronRight className="w-5 h-5" /></button>
                  <button onClick={onClose} className="grid place-items-center w-8 h-8 rounded-lg text-zinc-500 hover:bg-black/5 dark:hover:bg-white/5 transition" aria-label="Close"><IconClose className="w-5 h-5" /></button>
                </div>
              </div>
            </div>

            {/* body */}
            <div className="flex-1 overflow-y-auto tinybar p-5">
              {items.length === 0 ? (
                <div className="grid place-items-center h-full text-center px-6">
                  <div>
                    <div className="mx-auto grid place-items-center w-14 h-14 rounded-2xl bg-black/5 dark:bg-white/5 text-zinc-400 mb-3"><IconCalendar className="w-7 h-7" /></div>
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">Nothing goes out this day.</p>
                    <Button size="sm" variant="primary" className="mt-4" onPress={onGenerate}><IconWand className="w-4 h-4" /> Generate a batch</Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {items.map((v) => <DayReel key={v.slug} v={v} now={now} onOpen={onOpen} stats={v.video_id ? stats[v.video_id] : undefined} />)}
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function DayReel({ v, now, onOpen, stats }: { v: ScheduleVideo; now: number; onOpen: (v: ScheduleVideo) => void; stats?: VideoStats }) {
  const s = STATUS[v.status];
  const d = whenOf(v);
  const future = v.status === "scheduled" && v.publish_at && new Date(v.publish_at).getTime() > now;
  const playable = !!(v.output_url || v.youtube_url);
  return (
    <div className="group flex gap-3 rounded-2xl border border-black/5 dark:border-white/10 bg-white/60 dark:bg-white/[0.03] p-3 transition hover:ring-2 hover:ring-brand/40">
      <button onClick={() => onOpen(v)} disabled={!playable}
        className="relative shrink-0 w-[68px] h-[96px] rounded-xl overflow-hidden bg-zinc-900 grid place-items-center disabled:cursor-default">
        {v.poster ? <img src={v.poster} alt="" loading="lazy" className="w-full h-full object-cover" /> : <IconCat className="w-6 h-6 text-white/30" />}
        {playable && <span className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100 bg-black/30 transition"><IconPlay className="w-6 h-6 text-white" /></span>}
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-2">
          <p className="font-medium text-sm text-zinc-900 dark:text-white leading-snug line-clamp-2 flex-1">{cleanTitle(v)}</p>
          {v.youtube_url && (
            <a href={v.youtube_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
              className="shrink-0 grid place-items-center w-7 h-7 rounded-lg text-zinc-400 hover:text-red-500 hover:bg-red-500/10 transition" aria-label="Open on YouTube"><IconYoutube className="w-4 h-4" /></a>
          )}
        </div>
        <div className="mt-1.5 flex items-center gap-1.5 flex-wrap text-xs">
          <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium", s.chip)}><span className={cn("w-1.5 h-1.5 rounded-full", s.dot)} />{s.label}</span>
          {d && <span className="inline-flex items-center gap-1 text-zinc-500 dark:text-zinc-400"><IconClock className="w-3.5 h-3.5" />{v.status === "posted" && !v.publish_at ? "published" : timeLabel(d)}</span>}
          {future && <span className="text-zinc-400">in {fmtCountdown(new Date(v.publish_at!).getTime() - now)}</span>}
        </div>
        {v.place && <div className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">{sceneLabel(v.place)}</div>}
        {stats && v.status === "posted" && (
          <div className="mt-2 flex items-center gap-3 text-xs text-zinc-500 dark:text-zinc-400">
            <span className="inline-flex items-center gap-1"><IconEye className="w-3.5 h-3.5" />{fmtNum(stats.views)}</span>
            <span className="inline-flex items-center gap-1"><IconHeart className="w-3.5 h-3.5" />{fmtNum(stats.likes)}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function AgendaRow({ v, now, onOpen, stats }: { v: ScheduleVideo; now: number; onOpen: (v: ScheduleVideo) => void; stats?: VideoStats }) {
  const s = STATUS[v.status];
  const d = whenOf(v);
  const future = v.status === "scheduled" && v.publish_at && new Date(v.publish_at).getTime() > now;
  return (
    <div className="group flex items-center gap-3 rounded-2xl border border-black/5 dark:border-white/10 bg-white/50 dark:bg-white/[0.03] p-2.5 hover:ring-2 hover:ring-brand/40 transition">
      <button onClick={() => onOpen(v)} className="relative shrink-0 w-12 h-[68px] rounded-lg overflow-hidden bg-zinc-900 grid place-items-center">
        {v.poster ? <img src={v.poster} alt="" loading="lazy" className="w-full h-full object-cover" /> : <IconCat className="w-5 h-5 text-white/30" />}
        <span className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100 bg-black/30 transition"><IconPlay className="w-5 h-5 text-white" /></span>
      </button>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-sm text-zinc-900 dark:text-white truncate">{cleanTitle(v)}</p>
        <div className="mt-1 flex items-center gap-2 text-xs">
          <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium", s.chip)}><span className={cn("w-1.5 h-1.5 rounded-full", s.dot)} />{s.label}</span>
          {d && <span className="text-zinc-500 dark:text-zinc-400">{v.status === "posted" && !v.publish_at ? "published" : timeLabel(d)}</span>}
          {future && <span className="text-zinc-400">· in {fmtCountdown(new Date(v.publish_at!).getTime() - now)}</span>}
          {stats && v.status === "posted" && (
            <span className="inline-flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
              <span className="inline-flex items-center gap-1"><IconEye className="w-3.5 h-3.5" />{fmtNum(stats.views)}</span>
              <span className="inline-flex items-center gap-1"><IconHeart className="w-3.5 h-3.5" />{fmtNum(stats.likes)}</span>
            </span>
          )}
        </div>
      </div>
      {v.youtube_url && (
        <a href={v.youtube_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
          className="shrink-0 grid place-items-center w-9 h-9 rounded-lg text-zinc-400 hover:text-red-500 hover:bg-red-500/10 transition" aria-label="Open on YouTube">
          <IconYoutube className="w-5 h-5" />
        </a>
      )}
    </div>
  );
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full px-3 py-1.5 text-xs font-medium transition border",
        active
          ? "bg-brand/15 text-zinc-900 dark:text-white border-brand/40"
          : "border-transparent text-zinc-500 dark:text-zinc-400 hover:bg-black/5 dark:hover:bg-white/5",
      )}
    >
      {children}
    </button>
  );
}

function GeneratePanel({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [text, setText] = useState("");
  const [scene, setScene] = useState("home");
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const append = (l: string) => setLog((x) => [...x, l]);
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);

  const createDrafts = async () => {
    if (!lines.length) return;
    setBusy(true);
    for (const pov of lines) {
      try { const r = await api.draft(pov, scene); append(`+ draft ${r.slug}`); }
      catch (e) { append(`! ${pov}: ${(e as Error).message}`); }
    }
    append(`created ${lines.length} draft(s) — now hit "Render & schedule".`);
    setBusy(false);
  };

  const runBatch = () => {
    setBusy(true); append("$ starting batch…");
    const es = new EventSource(api.batchStreamUrl());
    es.onmessage = (e) => {
      const d = JSON.parse(e.data);
      if (d.line) append(d.line);
      if (d.done) { es.close(); setBusy(false); append("✓ batch complete"); onDone(); }
    };
    es.onerror = () => { es.close(); setBusy(false); append("— connection closed —"); };
  };

  return (
    <div className="mb-6 rounded-2xl border border-brand/30 bg-brand/[0.05] p-4 sm:p-5">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 font-display font-semibold text-zinc-900 dark:text-white"><IconWand className="w-4 h-4 text-brand" /> Generate a batch</div>
        <button onClick={onClose} className="text-zinc-400 hover:text-zinc-900 dark:hover:text-white" aria-label="Close"><IconClose className="w-5 h-5" /></button>
      </div>
      <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">One POV premise per line. Drafts get a generic reaction arc — refine them in the Stories tab for the funny stuff — then render + schedule onto the every-6h grid.</p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4}
        placeholder={"POV: you opened the camera on the wrong side\nPOV: your earbuds catch on a door handle"}
        className="w-full rounded-xl border border-black/10 dark:border-white/10 bg-white/70 dark:bg-black/30 p-3 text-sm text-zinc-900 dark:text-white outline-none focus:ring-2 focus:ring-brand/40 resize-y font-mono" />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="text-xs text-zinc-500 dark:text-zinc-400">Setting</label>
        <select value={scene} onChange={(e) => setScene(e.target.value)}
          className="rounded-lg border border-black/10 dark:border-white/10 bg-white/70 dark:bg-black/30 px-2 py-1.5 text-sm text-zinc-900 dark:text-white outline-none">
          {Object.keys(SCENES).filter((k) => k !== "others").map((k) => <option key={k} value={k}>{sceneLabel(k)}</option>)}
        </select>
        <div className="flex-1" />
        <Button size="sm" variant="ghost" isDisabled={busy || !lines.length} onPress={createDrafts}>
          Create {lines.length || ""} draft{lines.length === 1 ? "" : "s"}
        </Button>
        <Button size="sm" variant="primary" isDisabled={busy} onPress={runBatch}>
          {busy ? "Working…" : "Render & schedule pending"}
        </Button>
      </div>
      {log.length > 0 && (
        <pre className="mt-3 max-h-56 overflow-auto rounded-xl bg-black/90 text-zinc-200 text-[11px] leading-relaxed p-3 font-mono whitespace-pre-wrap">{log.join("\n")}</pre>
      )}
    </div>
  );
}

function Legend() {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
      {(["posted", "scheduled", "queued"] as VideoStatus[]).map((k) => (
        <span key={k} className="inline-flex items-center gap-1.5"><span className={cn("w-2 h-2 rounded-full", STATUS[k].dot)} />{STATUS[k].label}</span>
      ))}
      <span className="ml-auto inline-flex items-center gap-1.5"><IconClock className="w-3.5 h-3.5" /> auto-publishing every ~6h</span>
    </div>
  );
}
