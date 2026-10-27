//! Prime-time debate reels, drawn by fframes on the GPU.
//!
//! Every frame is an SVG tree built from `timeline.json`, which `engine/news_render.py`
//! writes next to the media it prepares (per-panelist green-screen tracks, blurred
//! backgrounds, the baked CCTV clip and the audio mix). The cats are keyed in
//! `shaders/key.sksl`. See docs/21-prime-time-debate.md.
use fframes::{
    AudioMap, AudioTimestamp::*, AudioTrack, Color, Duration, FFramesContext,
    FFramesSyncedVideoFrame, FontQuery, Frame, Shader, ShaderUniforms, Svgr, SyncVideoFrameInput,
    Video,
};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::sync::OnceLock;

pub const WIDTH: usize = 1080;
pub const HEIGHT: usize = 1920;
const W: f32 = WIDTH as f32;
const H: f32 = HEIGHT as f32;

// layout, matching the tile area the prep step bakes the CCTV for (1080 x 1036)
const TOP_H: f32 = 132.;
const HEAD_Y0: f32 = TOP_H;
const HEAD_Y1: f32 = 372.;
const TILE_Y0: f32 = 384.;
const TILE_Y1: f32 = 1420.;
const QUOTE_Y0: f32 = 1432.;
const QUOTE_Y1: f32 = 1690.;
const TICK_Y0: f32 = 1702.;
const TICK_Y1: f32 = 1798.;
const MARKET_Y0: f32 = 1806.;
const GUTTER: f32 = 8.;

const NAVY: &str = "#0a0f2c";
const RED: &str = "#ce0a12";
const YELLOW: &str = "#ffd600";
const INK: &str = "#0c0c10";
const IMPACT: &str = "Impact";
const SANS: &str = "Arial";
const MONO: &str = "Menlo";

// ── the script, as resolved by news_render.py ─────────────────────────────────
#[derive(Debug, Deserialize)]
pub struct Timeline {
    duration: f32,
    clock: String,
    market: String,
    panel: BTreeMap<String, Panelist>,
    stings: Vec<Sting>,
    layouts: Vec<Layout>,
    headlines: Vec<Line>,
    tickers: Vec<Line>,
    quotes: Vec<Quote>,
    speaks: Vec<Speak>,
    chaos: Vec<Span>,
    cctv: Vec<Cctv>,
    bars: Vec<Bars>,
}

#[derive(Debug, Deserialize)]
struct Panelist {
    name: String,
    role: String,
    studio: bool,
    fit: f32,
    aspect: f32,
    key: [f32; 3],
    #[serde(skip)]
    track: String,
    #[serde(skip)]
    bg: String,
}

#[derive(Debug, Deserialize)]
struct Sting {
    t: f32,
    until: f32,
    text: String,
    exclusive: bool,
}

#[derive(Debug, Deserialize)]
struct Layout {
    t: f32,
    tiles: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct Line {
    t: f32,
    text: String,
}

#[derive(Debug, Deserialize)]
struct Quote {
    t: f32,
    name: String,
    text: String,
}

#[derive(Debug, Deserialize)]
struct Speak {
    t: f32,
    until: f32,
    who: String,
}

#[derive(Debug, Deserialize)]
struct Span {
    t: f32,
    until: f32,
}

#[derive(Debug, Deserialize)]
struct Cctv {
    t: f32,
    until: f32,
    enhance: Option<f32>,
    label: String,
    clock: String,
    date: String,
}

#[derive(Debug, Deserialize)]
struct Bars {
    t: f32,
    who: String,
}

/// The latest item that has started (`t <= now`).
fn latest<T>(items: &[T], now: f32, at: impl Fn(&T) -> f32) -> Option<&T> {
    items.iter().filter(|e| at(e) <= now).last()
}

fn ease_out_back(x: f32) -> f32 {
    let c1 = 1.70158;
    1. + (c1 + 1.) * (x - 1.).powi(3) + c1 * (x - 1.).powi(2)
}

fn ease_out_cubic(x: f32) -> f32 {
    1. - (1. - x).powi(3)
}

/// Tile rects for n panelists: 1 | 2 side by side | 2x2 | 3x2.
fn grid(n: usize) -> Vec<(f32, f32, f32, f32)> {
    let (cols, rows) = match n {
        1 => (1, 1),
        2 => (2, 1),
        3 => (3, 1),
        4 => (2, 2),
        _ => (3, 2),
    };
    let tw = (W - GUTTER * (cols as f32 + 1.)) / cols as f32;
    let th = (TILE_Y1 - TILE_Y0 - GUTTER * (rows as f32 - 1.)) / rows as f32;
    (0..n)
        .map(|i| {
            let (c, r) = ((i % cols) as f32, (i / cols) as f32);
            (GUTTER + c * (tw + GUTTER), TILE_Y0 + r * (th + GUTTER), tw, th)
        })
        .collect()
}

fn track_input() -> SyncVideoFrameInput<'static> {
    SyncVideoFrameInput { start_from: 0., looping: false, editor_fallback_image: None }
}

pub struct DebateVideo {
    tl: Timeline,
    key: Shader,
    /// Headline font size + rows, measured once per headline.
    heads: Vec<OnceLock<(usize, Vec<String>)>>,
    /// Quote rows, measured once per quote.
    quotes: Vec<OnceLock<Vec<String>>>,
    market: Vec<(String, bool)>,
}

impl std::fmt::Debug for DebateVideo {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("DebateVideo").field("duration", &self.tl.duration).finish()
    }
}

impl DebateVideo {
    pub fn from_json(json: &str) -> Result<Self, serde_json::Error> {
        let mut tl: Timeline = serde_json::from_str(json)?;
        for (who, p) in tl.panel.iter_mut() {
            p.track = format!("track_{who}.mp4");
            p.bg = format!("bg_{who}.jpg");
        }
        let market = tl
            .market
            .split(" • ")
            .map(|s| (s.to_string(), s.contains('▲')))
            .collect();
        Ok(Self {
            heads: tl.headlines.iter().map(|_| OnceLock::new()).collect(),
            quotes: tl.quotes.iter().map(|_| OnceLock::new()).collect(),
            key: Shader::sksl(include_str!("shaders/key.sksl")),
            market,
            tl,
        })
    }

    pub fn duration_seconds(&self) -> f32 {
        self.tl.duration
    }

    fn width<'a>(frame: &mut Frame, ctx: &FFramesContext<'a, '_>, family: &'a str, size: usize, weight: u16, s: &'a str) -> f32 {
        let font = FontQuery { family, size, weight, ..Default::default() };
        frame.text_width(ctx, font, s).map_or(s.chars().count() as f32 * size as f32 * 0.55, |w| w as f32)
    }

    /// Greedy word wrap, measuring each word (words borrow from `self`, so they can be
    /// measured with the context's lifetime).
    fn wrap<'a>(frame: &mut Frame, ctx: &FFramesContext<'a, '_>, family: &'a str, size: usize, weight: u16, text: &'a str, max_w: f32) -> Vec<String> {
        let space = Self::width(frame, ctx, family, size, weight, " ");
        let mut rows: Vec<(String, f32)> = vec![(String::new(), 0.)];
        for word in text.split_whitespace() {
            let w = Self::width(frame, ctx, family, size, weight, word);
            let (row, rw) = rows.last_mut().unwrap();
            if row.is_empty() {
                row.push_str(word);
                *rw = w;
            } else if *rw + space + w <= max_w {
                row.push(' ');
                row.push_str(word);
                *rw += space + w;
            } else {
                rows.push((word.to_string(), w));
            }
        }
        rows.into_iter().map(|(r, _)| r).collect()
    }

    // ── tiles ─────────────────────────────────────────────────────────────────
    fn studio(&self, x: f32, y: f32, w: f32, h: f32) -> Svgr<'_> {
        let stripes: Vec<Svgr> = (0..((w / 120.) as usize + 1))
            .map(|i| {
                let sx = x + 60. + i as f32 * 120.;
                fframes::svgr!(<rect x={sx} y={y} width="14" height={h} fill="#4690ff" opacity="0.22" />)
            })
            .collect();
        let r = w.min(h) * 0.28;
        fframes::svgr!(
            <g>
                <rect x={x} y={y} width={w} height={h} fill="url(#studio)" />
                {stripes}
                <ellipse cx={x + w / 2.} cy={y + h * 0.42} rx={r} ry={r} fill="none" stroke="#78b4ff" stroke-width="5" opacity="0.7" />
                <ellipse cx={x + w / 2.} cy={y + h * 0.42} rx={r} ry={r * 0.22} fill="none" stroke="#78b4ff" stroke-width="2" opacity="0.6" />
                <text x={x + w / 2.} y={y + h * 0.9} font-family={IMPACT} font-size={w * 0.14} fill="#ffffff" opacity="0.14" text-anchor="middle">"MEOW 24×7"</text>
            </g>
        )
    }

    fn plate<'a>(&'a self, frame: &mut Frame, ctx: &FFramesContext<'a, '_>, p: &'a Panelist, x: f32, y: f32, w: f32, h: f32) -> Svgr<'a> {
        let fs = (w / 9.).clamp(30., 50.) as usize;
        let rs = (fs as f32 * 0.62) as usize;
        let nw = (Self::width(frame, ctx, IMPACT, fs, 400, &p.name) + 28.).min(w - 16.);
        let rw = (Self::width(frame, ctx, SANS, rs, 700, &p.role) + 24.).min(w - 16.);
        let ph = fs as f32 + 14. + rs as f32 + 12.;
        let (px, py) = (x, y + h - ph - 10.);
        fframes::svgr!(
            <g>
                <rect x={px} y={py} width={nw} height={fs as f32 + 14.} fill={RED} />
                <text x={px + 14.} y={py + fs as f32 + 3.} font-family={IMPACT} font-size={fs} fill="#ffffff">{p.name.as_str()}</text>
                <rect x={px} y={py + fs as f32 + 14.} width={rw} height={rs as f32 + 12.} fill="#ffffff" />
                <text x={px + 12.} y={py + fs as f32 + 14. + rs as f32 + 3.} font-family={SANS} font-weight="700" font-size={rs} fill={INK}>{p.role.as_str()}</text>
            </g>
        )
    }

    fn cat<'a>(&'a self, frame: &Frame, ctx: &FFramesContext<'a, '_>, p: &'a Panelist, x: f32, y: f32, w: f32, h: f32) -> Svgr<'a> {
        let input = track_input();
        let Some(video) = frame.get_synced_video_frame(ctx, &p.track, &input) else {
            return Svgr::empty();
        };
        let (vw, vh) = (video.width() as f32, video.height() as f32);
        let image = video.into_image();
        let layer = self.key.draw(
            frame,
            ShaderUniforms::new()
                .image("uSrc", &image)
                .float2("uSrcSize", vw, vh)
                .float3("uKey", p.key[0], p.key[1], p.key[2]),
        );
        let mut ch = h * p.fit;
        let mut cw = ch * p.aspect;
        if cw > w * 1.15 {
            cw = w * 1.15;
            ch = cw / p.aspect;
        }
        let (cx, cy) = (x + (w - cw) / 2., y + h - ch + h * 0.02);
        fframes::svgr!(<image href={layer.href()} x={cx} y={cy} width={cw} height={ch} />)
    }

    fn color_bars(&self, x: f32, y: f32, w: f32, h: f32) -> Svgr<'_> {
        const COLS: [&str; 7] = ["#c0c0c0", "#c0c000", "#00c0c0", "#00c000", "#c000c0", "#c00000", "#0000c0"];
        let bw = w / 7.;
        let top: Vec<Svgr> = COLS
            .iter()
            .enumerate()
            .map(|(i, c)| fframes::svgr!(<rect x={x + i as f32 * bw} y={y} width={bw + 0.5} height={h * 0.72} fill={*c} />))
            .collect();
        let mid: Vec<Svgr> = COLS
            .iter()
            .rev()
            .enumerate()
            .map(|(i, c)| {
                let fill = if i % 2 == 1 { *c } else { "#141414" };
                fframes::svgr!(<rect x={x + i as f32 * bw} y={y + h * 0.72} width={bw + 0.5} height={h * 0.08} fill={fill} />)
            })
            .collect();
        let fs = (w / 13.).max(18.);
        let bh = fs * 2.4;
        let cy = y + h * 0.36;
        fframes::svgr!(
            <g>
                {top}
                {mid}
                <rect x={x} y={y + h * 0.8} width={w} height={h * 0.2} fill="#101010" />
                <rect x={x + w * 0.06} y={cy - bh / 2.} width={w * 0.88} height={bh} fill="#000000" />
                <text x={x + w / 2.} y={cy - fs * 0.1} font-family={IMPACT} font-size={fs} fill="#ffffff" text-anchor="middle">"TECHNICAL DIFFICULTY"</text>
                <text x={x + w / 2.} y={cy + fs * 0.85} font-family={SANS} font-weight="700" font-size={fs * 0.55} fill={YELLOW} text-anchor="middle">"please stand by"</text>
            </g>
        )
    }

    fn tiles<'a>(&'a self, frame: &mut Frame, ctx: &FFramesContext<'a, '_>, t: f32, shake: (f32, f32), chaos: bool) -> Svgr<'a> {
        let layouts = &self.tl.layouts;
        let Some(li) = layouts.iter().rposition(|l| l.t <= t) else {
            return Svgr::empty();
        };
        let lay = &layouts[li];
        let targets = grid(lay.tiles.len());
        let prev: BTreeMap<&str, (f32, f32, f32, f32)> = if li > 0 {
            let p = &layouts[li - 1];
            p.tiles.iter().map(String::as_str).zip(grid(p.tiles.len())).collect()
        } else {
            BTreeMap::new()
        };
        let k = ease_out_cubic(((t - lay.t) / 0.3).clamp(0., 1.));
        let speaking = self.tl.speaks.iter().find(|s| s.t <= t && t < s.until);

        let mut out = Vec::new();
        for (who, rect) in lay.tiles.iter().zip(targets) {
            let Some(p) = self.tl.panel.get(who) else { continue };
            let old = prev.get(who.as_str()).copied().unwrap_or((rect.0, TILE_Y1, rect.2, rect.3));
            let lerp = |a: f32, b: f32| a + (b - a) * k;
            let (x, y, w, h) = (
                lerp(old.0, rect.0) + shake.0,
                lerp(old.1, rect.1) + shake.1,
                lerp(old.2, rect.2),
                lerp(old.3, rect.3),
            );
            let clip_id = format!("tile-{who}");
            let off_air = self.tl.bars.iter().any(|b| b.who == *who && b.t <= t);
            let body = if off_air {
                self.color_bars(x, y, w, h)
            } else {
                let bg = if p.studio {
                    self.studio(x, y, w, h)
                } else {
                    ctx.get_image(&p.bg).map_or_else(Svgr::empty, |img| {
                        fframes::svgr!(<image href={img.href()} x={x} y={y} width={w} height={h} preserveAspectRatio="xMidYMid slice" />)
                    })
                };
                let dim = speaking.is_some_and(|s| s.who != *who);
                let cat = self.cat(frame, ctx, p, x, y, w, h);
                let plate = self.plate(frame, ctx, p, x, y, w, h);
                fframes::svgr!(
                    <g>
                        {bg}
                        {cat}
                        <rect x={x} y={y} width={w} height={h} fill="#000000" opacity={if dim { 0.25 } else { 0. }} />
                        {plate}
                    </g>
                )
            };
            let hot = chaos || speaking.is_some_and(|s| s.who == *who);
            let (stroke, sw) = if hot { (YELLOW, 7.) } else { ("#283259", 3.) };
            out.push(fframes::svgr!(
                <g>
                    <clipPath id={clip_id.clone()}>
                        <rect x={x} y={y} width={w} height={h} />
                    </clipPath>
                    <g clip-path={format!("url(#{clip_id})")}>{body}</g>
                    <rect x={x - 3.} y={y - 3.} width={w + 5.} height={h + 5.} fill="none" stroke={stroke} stroke-width={sw} />
                </g>
            ));
        }
        fframes::svgr!(<g>{out}</g>)
    }

    fn cctv<'a>(&'a self, frame: &Frame, ctx: &FFramesContext<'a, '_>, c: &'a Cctv, t: f32) -> Svgr<'a> {
        let input = SyncVideoFrameInput { start_from: c.t, looping: false, editor_fallback_image: None };
        let footage = frame.get_synced_video_frame(ctx, "cctv.mp4", &input).map_or_else(Svgr::empty, |v| {
            let img = v.into_image();
            fframes::svgr!(<image href={img.href()} x="0" y={TILE_Y0} width={W} height={TILE_Y1 - TILE_Y0} />)
        });
        let (h, y0) = (TILE_Y1 - TILE_Y0, TILE_Y0);
        let mut parts = vec![footage];
        if let Some(te) = c.enhance.filter(|te| t >= *te) {
            let m = 70.;
            for (ax, ay, sx, sy) in [(m, m, 1., 1.), (W - m, m, -1., 1.), (m, h - m, 1., -1.), (W - m, h - m, -1., -1.)] {
                parts.push(fframes::svgr!(
                    <path d={format!("M{} {} L{} {} M{} {} L{} {}", ax, y0 + ay, ax + 70. * sx, y0 + ay, ax, y0 + ay, ax, y0 + ay + 70. * sy)}
                        stroke="#ffffff" stroke-width="6" fill="none" />
                ));
            }
            if ((t - te) * 4.) as i32 % 2 == 0 {
                parts.push(fframes::svgr!(
                    <text x={W / 2.} y={y0 + h - 100.} font-family={MONO} font-size="64" fill="#ffffff" text-anchor="middle">"ENHANCE"</text>
                ));
            }
        }
        let secs = {
            let mut it = c.clock.split(':').map(|x| x.parse::<i32>().unwrap_or(0));
            let (hh, mm, ss) = (it.next().unwrap_or(0), it.next().unwrap_or(0), it.next().unwrap_or(0));
            hh * 3600 + mm * 60 + ss + (t - c.t) as i32
        };
        let stamp = format!("{}  {:02}:{:02}:{:02}", c.date, secs / 3600, secs / 60 % 60, secs % 60);
        let rec = if (t * 2.) as i32 % 2 == 0 { 1. } else { 0. };
        fframes::svgr!(
            <g>
                {parts}
                <text x="28" y={y0 + 60.} font-family={MONO} font-size="40" fill="#ebffeb">{c.label.as_str()}</text>
                <circle cx={W - 175.} cy={y0 + 49.} r="15" fill="#ff2828" opacity={rec} />
                <text x={W - 148.} y={y0 + 60.} font-family={MONO} font-size="40" fill="#ebffeb">"REC"</text>
                <text x="28" y={y0 + h - 30.} font-family={MONO} font-size="40" fill="#ebffeb">{stamp}</text>
            </g>
        )
    }

    // ── chrome ────────────────────────────────────────────────────────────────
    fn sting<'a>(&'a self, s: &'a Sting, t: f32) -> Svgr<'a> {
        let age = t - s.t;
        let (base, stripe, fill) = if s.exclusive { ("#141414", "#3c3200", YELLOW) } else { ("#b40000", "#dc1414", "#ffffff") };
        let off = (age * 900.) % 160.;
        let stripes: Vec<Svgr> = (-4..20)
            .map(|i| {
                let x = i as f32 * 160. + off;
                let pts = format!("{},0 {},0 {},{} {},{}", x, x + 70., x - 500., H, x - 570., H);
                fframes::svgr!(<polygon points={pts} fill={stripe} />)
            })
            .collect();
        let sc = 1.9 - 0.9 * ease_out_back((age / 0.28).min(1.));
        let words: Vec<&str> = s.text.split_whitespace().collect();
        let fs = 190.;
        let y0 = H / 2. - words.len() as f32 * fs * 0.5 + fs * 0.85;
        let lines: Vec<Svgr> = words
            .iter()
            .enumerate()
            .map(|(i, wd)| {
                let y = y0 + i as f32 * fs;
                fframes::svgr!(
                    <g>
                        <text x={W / 2. + 6.} y={y + 8.} font-family={IMPACT} font-size={fs} fill="#000000" text-anchor="middle">{*wd}</text>
                        <text x={W / 2.} y={y} font-family={IMPACT} font-size={fs} fill={fill} stroke="#000000" stroke-width="6" paint-order="stroke" text-anchor="middle">{*wd}</text>
                    </g>
                )
            })
            .collect();
        let zoom = format!("translate({} {}) scale({})", W / 2. * (1. - sc), H / 2. * (1. - sc), sc);
        let flash = if age < 0.1 { 1. - age / 0.1 } else { 0. };
        fframes::svgr!(
            <g>
                <rect width={W} height={H} fill={base} />
                {stripes}
                <g transform={zoom}>{lines}</g>
                <rect width={W} height={H} fill="#ffffff" opacity={flash} />
            </g>
        )
    }

    fn headline<'a>(&'a self, frame: &mut Frame, ctx: &FFramesContext<'a, '_>, t: f32, shake: (f32, f32)) -> Svgr<'a> {
        let band = fframes::svgr!(
            <g>
                <rect x="0" y={HEAD_Y0} width={W} height={HEAD_Y1 - HEAD_Y0} fill={RED} />
                <rect x="0" y={HEAD_Y1 - 14.} width={W} height="14" fill={YELLOW} />
            </g>
        );
        let Some(i) = self.tl.headlines.iter().rposition(|h| h.t <= t) else { return band };
        let hl = &self.tl.headlines[i];
        let (size, rows) = self.heads[i].get_or_init(|| {
            let mut size = 104;
            loop {
                let rows = Self::wrap(frame, ctx, IMPACT, size, 400, &hl.text, W - 80.);
                if rows.len() <= 2 || size <= 46 {
                    return (size, rows);
                }
                size -= 6;
            }
        });
        let age = t - hl.t;
        let off = if age < 0.22 { (1. - ease_out_back(age / 0.22)) * -W } else { 0. };
        let lh = *size as f32 * 1.02;
        let top = (HEAD_Y0 + HEAD_Y1 - 14.) / 2. - lh * rows.len() as f32 / 2. + shake.1;
        let texts: Vec<Svgr> = rows
            .iter()
            .enumerate()
            .map(|(j, r)| {
                let y = top + lh * (j as f32 + 0.86);
                let x = 40. + off + shake.0;
                fframes::svgr!(
                    <g>
                        <text x={x + 4.} y={y + 5.} font-family={IMPACT} font-size={*size} fill="#5a0000">{r.as_str()}</text>
                        <text x={x} y={y} font-family={IMPACT} font-size={*size} fill="#ffffff">{r.as_str()}</text>
                    </g>
                )
            })
            .collect();
        fframes::svgr!(<g>{band}{texts}</g>)
    }

    fn top(&self, t: f32) -> Svgr<'_> {
        let live = if (t * 1.6) as i32 % 2 == 0 { 1. } else { 0. };
        fframes::svgr!(
            <g>
                <rect x="0" y="0" width={W} height={TOP_H} fill={NAVY} />
                <rect x="28" y="26" width="272" height="80" rx="12" fill={RED} />
                <text x="44" y="94" font-family={IMPACT} font-size="68" fill="#ffffff">"MEOW"</text>
                <text x="212" y="88" font-family={IMPACT} font-size="44" fill={YELLOW}>"24×7"</text>
                <circle cx={W - 317.} cy="65" r="13" fill="#ff2828" opacity={live} />
                <text x={W - 292.} y="90" font-family={IMPACT} font-size="54" fill="#ffffff">"LIVE"</text>
                <text x={W - 160.} y="80" font-family={SANS} font-weight="700" font-size="36" fill="#c8d2ff">{self.tl.clock.as_str()}</text>
            </g>
        )
    }

    fn quote<'a>(&'a self, frame: &mut Frame, ctx: &FFramesContext<'a, '_>, t: f32) -> Svgr<'a> {
        let boxed = fframes::svgr!(<rect x="0" y={QUOTE_Y0} width={W} height={QUOTE_Y1 - QUOTE_Y0} fill="#ffffff" />);
        let Some(i) = self.tl.quotes.iter().rposition(|q| q.t <= t) else { return boxed };
        let q = &self.tl.quotes[i];
        let rows = self.quotes[i].get_or_init(|| {
            let mut rows = Self::wrap(frame, ctx, SANS, 60, 700, &q.text, W - 110.);
            rows.truncate(2);
            if let Some(first) = rows.first_mut() {
                first.insert(0, '\u{201c}');
            }
            if let Some(last) = rows.last_mut() {
                last.push('\u{201d}');
            }
            rows
        });
        let nw = Self::width(frame, ctx, IMPACT, 48, 400, &q.name) + 44.;
        let k = ((t - q.t) / 0.15).clamp(0., 1.);
        let texts: Vec<Svgr> = rows
            .iter()
            .enumerate()
            .map(|(j, r)| {
                let y = QUOTE_Y0 + 76. + 60. + j as f32 * 74. + (1. - k) * 20.;
                fframes::svgr!(<text x="36" y={y} font-family={SANS} font-weight="700" font-size="60" fill={INK} opacity={k}>{r.as_str()}</text>)
            })
            .collect();
        fframes::svgr!(
            <g>
                {boxed}
                <rect x="0" y={QUOTE_Y0} width={nw} height="70" fill={RED} />
                <text x="22" y={QUOTE_Y0 + 56.} font-family={IMPACT} font-size="48" fill="#ffffff">{q.name.as_str()}</text>
                {texts}
            </g>
        )
    }

    fn ticker<'a>(&'a self, frame: &mut Frame, ctx: &FFramesContext<'a, '_>, t: f32, chaos: bool) -> Svgr<'a> {
        let mut parts = vec![fframes::svgr!(<rect x="0" y={TICK_Y0} width={W} height={TICK_Y1 - TICK_Y0} fill="#ffffff" />)];
        if let Some(tk) = latest(&self.tl.tickers, t, |l| l.t) {
            let speed = if chaos { 260. } else { 140. };
            let sep = "   •   ";
            let sw = Self::width(frame, ctx, SANS, 44, 700, &tk.text) + Self::width(frame, ctx, SANS, 44, 700, sep);
            let mut x = 300. - (t * speed) % sw;
            while x < W {
                parts.push(fframes::svgr!(
                    <text x={x} y={TICK_Y0 + 64.} font-family={SANS} font-weight="700" font-size="44" fill={INK}>{tk.text.as_str()}</text>
                ));
                x += sw;
            }
        }
        let arrow = format!("280,{} 310,{} 280,{}", TICK_Y0, (TICK_Y0 + TICK_Y1) / 2., TICK_Y1);
        fframes::svgr!(
            <g>
                {parts}
                <rect x="0" y={TICK_Y0} width="280" height={TICK_Y1 - TICK_Y0} fill={YELLOW} />
                <polygon points={arrow} fill={YELLOW} />
                <text x="22" y={TICK_Y0 + 70.} font-family={IMPACT} font-size="60" fill={INK}>"BREAKING"</text>
            </g>
        )
    }

    fn market<'a>(&'a self, frame: &mut Frame, ctx: &FFramesContext<'a, '_>, t: f32) -> Svgr<'a> {
        let widths: Vec<f32> = self.market.iter().map(|(s, _)| Self::width(frame, ctx, SANS, 36, 600, s) + 70.).collect();
        let total: f32 = widths.iter().sum();
        let mut items = Vec::new();
        if total > 0. {
            let mut x = -((t * 90.) % total);
            'outer: loop {
                for ((s, up), w) in self.market.iter().zip(&widths) {
                    if x > W {
                        break 'outer;
                    }
                    let fill = if *up { "#5ae678" } else { "#ff5a5a" };
                    items.push(fframes::svgr!(
                        <text x={x} y={MARKET_Y0 + 66.} font-family={SANS} font-weight="600" font-size="36" fill={fill}>{s.as_str()}</text>
                    ));
                    x += w;
                }
            }
        }
        fframes::svgr!(
            <g>
                <rect x="0" y={MARKET_Y0} width={W} height={H - MARKET_Y0} fill={NAVY} />
                {items}
            </g>
        )
    }
}

impl Video for DebateVideo {
    const FPS: usize = 30;
    const WIDTH: usize = WIDTH;
    const HEIGHT: usize = HEIGHT;
    const BACKGROUND_COLOR: Color = Color::BLACK;

    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(self.tl.duration)
    }

    fn audio(&self) -> AudioMap<'_> {
        AudioMap::from([AudioTrack::new("audio.wav", Second(0.)..Eof)])
    }

    fn render_frame<'a>(&'a self, mut frame: Frame, ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let body = if let Some(s) = self.tl.stings.iter().find(|s| s.t <= t && t < s.until) {
            self.sting(s, t)
        } else {
            let chaos = self.tl.chaos.iter().any(|c| c.t <= t && t < c.until);
            let shake = if chaos {
                // deterministic per-frame jitter
                let h = (frame.index as u32).wrapping_mul(2_654_435_761);
                (((h >> 8) % 29) as f32 - 14., ((h >> 16) % 21) as f32 - 10.)
            } else {
                (0., 0.)
            };
            let middle = match self.tl.cctv.iter().find(|c| c.t <= t && t < c.until) {
                Some(c) => self.cctv(&frame, ctx, c, t),
                None => self.tiles(&mut frame, ctx, t, shake, chaos),
            };
            let headline = self.headline(&mut frame, ctx, t, shake);
            let quote = self.quote(&mut frame, ctx, t);
            let ticker = self.ticker(&mut frame, ctx, t, chaos);
            let market = self.market(&mut frame, ctx, t);
            fframes::svgr!(
                <g>
                    <rect width={W} height={H} fill={NAVY} />
                    {middle}
                    {headline}
                    {self.top(t)}
                    {quote}
                    {ticker}
                    {market}
                </g>
            )
        };
        fframes::svgr!(
            <svg xmlns="http://www.w3.org/2000/svg" viewBox={format!("0 0 {WIDTH} {HEIGHT}")} width={WIDTH} height={HEIGHT}>
                <defs>
                    <linearGradient id="studio" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#081e5a" />
                        <stop offset="1" stop-color="#1c46a0" />
                    </linearGradient>
                </defs>
                {body}
            </svg>
        )
    }
}
