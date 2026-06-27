// Typed client for engine/server.py.

export interface Clip {
  id: string;
  file: string;
  title: string;
  duration: number;
  width: number;
  height: number;
  orientation: "portrait" | "landscape" | "square";
  key_color: string;
  primary: string;
  emotions: string[];
  action: string;
  sound: string;
  use_for: string;
  quality: "good" | "ok" | "partial" | "low" | "avoid";
  note: string;
  frame: string;
  clip: string;
}

export interface StorySummary {
  slug: string;
  title: string;
  pov: string;
  output: string;
  beats: number;
  outro: string;
}

export interface Resolved {
  id: string;
  primary: string;
  quality: Clip["quality"];
  frame: string;
}

export interface CastMember {
  name?: string;
  want?: string[];
  query?: string;
  clip?: string;
  size?: number;
  resolved?: Resolved;
  matched?: string[];
}

export interface Beat {
  action?: string;
  card?: string;
  dur?: number;
  bg?: { img?: string; place?: string; image?: string; palette?: string };
  cast?: CastMember[];
}

export interface Story {
  title?: string;
  output?: string;
  pov?: string;
  outro?: string;
  canvas?: { w: number; h: number; fps: number };
  beats: Beat[];
  [k: string]: unknown;
}

export interface Output {
  name: string;
  url: string;
  size: number;
  mtime: number;
  duration: number;
  poster: string | null;
}

export interface MatchResult {
  score: number;
  matched: string[];
  id: string;
  primary: string;
  quality: Clip["quality"];
  emotions: string[];
  duration: number;
  orientation: Clip["orientation"];
  frame: string;
  clip: string;
}

export type VideoStatus = "posted" | "scheduled" | "queued" | "authored";

export interface ScheduleVideo {
  slug: string;
  sort_order: number;
  pov: string;
  title: string;
  description: string;
  tags: string[];
  file: string;
  status: VideoStatus;
  posted: string | null;
  publish_at: string | null;
  video_id: string | null;
  output_url: string | null;
  poster: string | null;
  youtube_url: string | null;
  place: string | null;
}

export interface Schedule {
  channel: { name?: string; url?: string };
  defaults: { privacy?: string; categoryId?: string; made_for_kids?: boolean };
  videos: ScheduleVideo[];
}

export interface VideoStats { views: number; likes: number; comments: number; privacy: string }
export interface Analytics {
  stats?: Record<string, VideoStats>;
  error?: "reauth" | "failed";
  detail?: string;
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

export const api = {
  catalog: () => get<Clip[]>("/api/catalog"),
  scenes: () => get<{ name: string; url: string }[]>("/api/scenes"),
  stories: () => get<StorySummary[]>("/api/stories"),
  story: (slug: string) => get<{ slug: string; raw: Story }>(`/api/stories/${slug}`),
  outputs: () => get<Output[]>("/api/outputs"),
  schedule: () => get<Schedule>("/api/schedule"),
  analytics: () => get<Analytics>("/api/analytics"),
  reschedule: async (slug: string, publish_at: string) => {
    const r = await fetch(`/api/schedule/${slug}/reschedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ publish_at }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
  },
  match: (want: string, query: string, limit = 18) =>
    get<MatchResult[]>(
      `/api/match?want=${encodeURIComponent(want)}&query=${encodeURIComponent(query)}&limit=${limit}`,
    ),
  saveStory: async (slug: string, story: Story) => {
    const r = await fetch(`/api/stories/${slug}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(story),
    });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    return r.json();
  },
  renderStreamUrl: (slug: string) => `/api/render/${slug}/stream`,
};

export function fmtBytes(n: number): string {
  if (n > 1e6) return `${(n / 1e6).toFixed(1)} MB`;
  if (n > 1e3) return `${(n / 1e3).toFixed(0)} KB`;
  return `${n} B`;
}

export function fmtDur(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return m ? `${m}:${String(sec).padStart(2, "0")}` : `${s.toFixed(1)}s`;
}

export function timeAgo(mtime: number): string {
  const d = Date.now() / 1000 - mtime;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
}
