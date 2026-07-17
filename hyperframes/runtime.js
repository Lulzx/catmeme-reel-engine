/*
 * HyperFrames runtime for wojak cat sagas — the render backend that replaced
 * Remotion. Given a manifest (window.__MANIFEST, same shape as the old
 * remotion/src/schema.ts) it builds the DOM under #stage and ONE paused GSAP
 * timeline, then registers it on window.__timelines[manifest.id].
 *
 * Every Remotion component's useCurrentFrame() body is ported near-verbatim as a
 * closed-form function of frame, run inside a per-scene "driver" tween's onUpdate
 * (a plain object tweened 0->durFrames with ease:"none", so its value IS the
 * scene-local frame). That pattern is seek-safe: HyperFrames seeks the timeline
 * to each frame and screenshots, and onUpdate reproduces identical state per time.
 *
 * Audio and camera shots are computed in Node (hyperframes/shots.mjs) and shipped
 * as data: <audio> elements are STATIC in index.html (HyperFrames muxes only
 * static media, not script-injected), and per-scene camera shots arrive as
 * window.__SHOTS. This runtime only builds visuals + the timeline.
 *
 * Determinism: no Date.now / Math.random (shots are precomputed & seeded; shake/
 * bob are closed-form sines; springs use gsap.parseEase).
 */
(function () {
  const M = window.__MANIFEST;
  const FPS = M.fps;
  const W = M.width;
  const H = M.height;
  const stage = document.getElementById("stage");

  // Remotion spring() -> GSAP back.out(N) (per remotion-to-hyperframes timing.md).
  // Character enter spring{damping:12,stiffness:140} and the red arrow
  // spring{damping:11,stiffness:130} both read as a snappy overshoot.
  const springChar = gsap.parseEase("back.out(1.4)");
  const springArrow = gsap.parseEase("back.out(1.3)");
  const SPRING_FRAMES = 0.7 * FPS; // ~settle time of the Remotion springs

  const lerp = (a, b, t) => a + (b - a) * t;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const cubicInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const asset = (p) => p; // assetsBase is "" locally; paths are build-dir relative

  // Remotion interpolate() with clamped extrapolation (used for opacity ramps).
  function interp(x, xs, ys) {
    if (x <= xs[0]) return ys[0];
    for (let i = 1; i < xs.length; i++) {
      if (x <= xs[i]) return lerp(ys[i - 1], ys[i], (x - xs[i - 1]) / (xs[i] - xs[i - 1]));
    }
    return ys[ys.length - 1];
  }

  const px = (n) => `${n}px`;
  function el(tag, style, props) {
    const e = document.createElement(tag);
    if (style) Object.assign(e.style, style);
    if (props) Object.assign(e, props);
    return e;
  }

  const LABEL_FONT = '"Arial Black", Impact, system-ui, sans-serif';
  const CAPTION_FONT = '"Helvetica Neue", Arial, system-ui, sans-serif';

  // ---- Background (static: flat gradient / blurred image + tint + vignette) ----
  function buildBackground(bg) {
    const wrap = el("div", { position: "absolute", inset: "0", width: px(W), height: px(H) });
    const grade = bg.grade;
    if (bg.kind === "flat") {
      const c1 = bg.color || "#2b2b3a";
      const background = bg.color2 ? `linear-gradient(180deg, ${c1} 0%, ${bg.color2} 100%)` : c1;
      wrap.appendChild(el("div", { position: "absolute", inset: "0", background }));
    } else {
      const f = grade && grade.filter && grade.filter !== "none" ? grade.filter + " " : "";
      wrap.appendChild(
        el("img", {
          position: "absolute", inset: "0", width: "100%", height: "100%",
          objectFit: "cover", filter: `${f}blur(2.4px)`,
        }, { src: asset(bg.src || "") })
      );
    }
    if (grade && grade.tintOpacity > 0) {
      wrap.appendChild(el("div", {
        position: "absolute", inset: "0", backgroundColor: grade.tint,
        opacity: String(grade.tintOpacity), mixBlendMode: grade.blend || "normal",
      }));
    }
    const vig = grade ? grade.vignette : bg.kind === "flat" ? 0.3 : 0.35;
    if (vig > 0) {
      wrap.appendChild(el("div", {
        position: "absolute", inset: "0",
        background: `radial-gradient(120% 95% at 50% 42%, rgba(0,0,0,0) 38%, rgba(0,0,0,${vig}) 100%)`,
      }));
    }
    return wrap;
  }

  // ---- Character (entrance spring + bob + flip + label; sprite / PNG sequence) ----
  // Returns { nodes:[...], update(frame) }. Nodes are appended by the caller.
  // A container div carries the transform/opacity; inside is either one <img>
  // (static sprite) or a preloaded opacity-stack of every sequence frame
  // (animated) — stacking avoids racing the browser's async image decode when a
  // frame is captured, which a per-frame img.src swap would risk.
  function buildCharacter(ch) {
    const { x, y, width, height } = ch.rect;
    const animated = ch.kind === "animated" && ch.seqCount && ch.seqFps;
    const img = el("div", {
      position: "absolute", left: px(x), top: px(y), width: px(width), height: px(height),
      transformOrigin: "center bottom",
      filter: `${ch.filter && ch.filter !== "none" ? ch.filter + " " : ""}drop-shadow(0 16px 26px rgba(0,0,0,0.55))`,
    });
    let frames = null;
    if (animated) {
      frames = [];
      for (let i = 0; i < ch.seqCount; i++) {
        const f = el("img", {
          position: "absolute", inset: "0", width: "100%", height: "100%",
          objectFit: "contain", opacity: i === 0 ? "1" : "0",
        }, { src: asset(`${ch.src}/${String(i + 1).padStart(4, "0")}.png`) });
        frames.push(f);
        img.appendChild(f);
      }
    } else {
      img.appendChild(el("img", {
        position: "absolute", inset: "0", width: "100%", height: "100%", objectFit: "contain",
      }, { src: asset(ch.src) }));
    }
    let curFrame = 0;

    let label = null;
    if (ch.label) {
      label = el("div", {
        position: "absolute", left: px(x), top: px(y + height * 0.06), width: px(width),
        textAlign: "center", fontFamily: LABEL_FONT, fontSize: "54px", color: "#fff",
        letterSpacing: "1px",
        textShadow: "0 0 6px #000, 3px 3px 0 #000, -3px 3px 0 #000, 3px -3px 0 #000, -3px -3px 0 #000",
      });
      label.textContent = ch.label;
    }

    function update(frame) {
      const p = springChar(clamp(frame / SPRING_FRAMES, 0, 1));
      let tx = 0, ty = 0, scale = 1, opacity = 1;
      switch (ch.enter) {
        case "slideLeft":
          tx = lerp(-width * 0.6, 0, p); opacity = interp(p, [0, 0.4, 1], [0, 1, 1]); break;
        case "slideRight":
          tx = lerp(width * 0.6, 0, p); opacity = interp(p, [0, 0.4, 1], [0, 1, 1]); break;
        case "bounce":
          ty = lerp(-height * 0.5, 0, p); opacity = interp(p, [0, 0.3, 1], [0, 1, 1]); break;
        case "pop":
          scale = lerp(0.6, 1, p); opacity = interp(p, [0, 0.5, 1], [0, 1, 1]); break;
        default:
          break;
      }
      const bobY = ty + Math.sin((frame / FPS) * 1.7) * 1.5;
      img.style.transform =
        `translate(${tx}px, ${bobY}px) scale(${scale})${ch.flip ? " scaleX(-1)" : ""}`;
      img.style.opacity = String(opacity);
      if (animated) {
        const idx = Math.min(ch.seqCount - 1, Math.floor((frame / FPS) * ch.seqFps) % ch.seqCount);
        if (idx !== curFrame) {
          frames[curFrame].style.opacity = "0";
          frames[idx].style.opacity = "1";
          curFrame = idx;
        }
      }
      if (label) {
        label.style.transform = `translate(${tx}px, ${bobY}px)`;
        label.style.opacity = String(opacity);
      }
    }

    update(0);
    return { nodes: label ? [img, label] : [img], update };
  }

  // ---- Camera (interpolates precomputed shots + decaying-sine shake) ----
  // Builds the camera world (bg + characters), returns { node, update }.
  // `shots` are precomputed in Node (hyperframes/shots.mjs) and passed in.
  function buildCameraScene(scene, shots) {
    const viewport = el("div", {
      position: "absolute", inset: "0", overflow: "hidden", backgroundColor: "#000",
    });
    const world = el("div", {
      position: "absolute", width: px(W), height: px(H), transformOrigin: "0 0",
      filter: "saturate(1.22) contrast(1.07)",
    });
    world.appendChild(buildBackground(scene.background));
    const charUpdaters = [];
    for (const ch of scene.characters || []) {
      const built = buildCharacter(ch);
      built.nodes.forEach((n) => world.appendChild(n));
      charUpdaters.push(built.update);
    }
    viewport.appendChild(world);

    function update(frame) {
      let shot = shots[shots.length - 1];
      for (const s of shots) {
        if (frame >= s.start && frame < s.start + s.dur) { shot = s; break; }
      }
      const into = frame - shot.start;
      const p = cubicInOut(clamp(into / shot.dur, 0, 1));
      const scale = lerp(shot.from.scale, shot.to.scale, p);
      const fx = lerp(shot.from.fx, shot.to.fx, p);
      const fy = lerp(shot.from.fy, shot.to.fy, p);
      let tx = clamp(W / 2 - fx * scale, W - W * scale, 0);
      let ty = clamp(H / 2 - fy * scale, H - H * scale, 0);
      const amp = shot.shake * Math.max(0, 1 - into / 6);
      tx += Math.sin(into * 2.4) * amp;
      ty += Math.cos(into * 1.8) * amp;
      world.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
      charUpdaters.forEach((u) => u(frame));
    }

    update(0);
    return { node: viewport, update };
  }

  // ---- Transformation (before/after split panels + spring red arrow + seam) ----
  function buildTransformation(scene) {
    const root = el("div", { position: "absolute", inset: "0", backgroundColor: "#000" });
    const updaters = [];

    (scene.panels || []).forEach((panel, pi) => {
      const side = pi === 0 ? "left" : "right";
      const pane = el("div", {
        position: "absolute", inset: "0",
        clipPath: side === "left" ? "inset(0 50% 0 0)" : "inset(0 0 0 50%)",
      });
      pane.appendChild(buildBackground(panel.background));
      const built = buildCharacter(panel.character);
      built.nodes.forEach((n) => pane.appendChild(n));
      updaters.push(built.update);
      if (panel.label) {
        const lab = el("div", {
          position: "absolute", top: "54px", left: side === "left" ? "0" : "50%", width: "50%",
          textAlign: "center", fontFamily: LABEL_FONT, fontSize: "58px", color: "#fff",
          letterSpacing: "2px",
          textShadow: "3px 3px 0 #000, -3px 3px 0 #000, 3px -3px 0 #000, -3px -3px 0 #000",
        });
        lab.textContent = panel.label;
        pane.appendChild(lab);
      }
      root.appendChild(pane);
    });

    // center seam
    const seamWrap = el("div", {
      position: "absolute", inset: "0", display: "flex",
      justifyContent: "center", alignItems: "center",
    });
    seamWrap.appendChild(el("div", { width: "6px", height: "100%", background: "rgba(255,255,255,0.85)" }));
    root.appendChild(seamWrap);

    // red arrow (spring pop)
    const arrowWrap = el("div", {
      position: "absolute", inset: "0", display: "flex",
      justifyContent: "center", alignItems: "center",
    });
    arrowWrap.innerHTML =
      '<svg width="360" height="200" viewBox="0 0 360 200" style="filter:drop-shadow(0 6px 10px rgba(0,0,0,0.5))">' +
      '<path d="M30 120 C 120 40, 230 40, 300 95 L 300 60 L 350 110 L 300 160 L 300 125 C 230 80, 130 80, 55 150 Z" ' +
      'fill="#ff2b2b" stroke="#fff" stroke-width="6" stroke-linejoin="round"/></svg>';
    const svg = arrowWrap.querySelector("svg");
    root.appendChild(arrowWrap);
    updaters.push((frame) => {
      const p = springArrow(clamp(frame / (0.6 * FPS), 0, 1));
      svg.style.transform = `scale(${0.4 + 0.6 * p})`;
    });

    updaters.forEach((u) => u(0));
    return { node: root, update: (frame) => updaters.forEach((u) => u(frame)) };
  }

  // ---- Captions (word-synced highlight groups) + ActionCaption (pinned line) ----
  const WORDS_PER_GROUP = 5;
  function buildCaptions(tokens) {
    const words = (tokens || []).filter((t) => /[A-Za-z0-9]/.test(t.text));
    const wrap = el("div", {
      position: "absolute", inset: "0", display: "flex",
      justifyContent: "flex-end", alignItems: "center", flexDirection: "column",
      paddingBottom: "92px", pointerEvents: "none",
    });
    if (!words.length) return { node: wrap, update: () => {} };
    const row = el("div", {
      display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0 12px",
      maxWidth: "74%", fontFamily: CAPTION_FONT, fontWeight: "700", fontSize: "46px",
      lineHeight: "1.2", letterSpacing: "0.2px",
    });
    wrap.appendChild(row);

    function update(frame) {
      const ms = (frame / FPS) * 1000;
      let activeIdx = words.findIndex((t) => ms >= t.startMs && ms < t.endMs);
      if (activeIdx === -1) activeIdx = ms < words[0].startMs ? 0 : words.length - 1;
      const groupIdx = Math.floor(activeIdx / WORDS_PER_GROUP);
      const start = groupIdx * WORDS_PER_GROUP;
      const group = words.slice(start, start + WORDS_PER_GROUP);
      const appear = interp(ms, [group[0].startMs - 80, group[0].startMs + 70], [0.35, 1]);
      row.style.opacity = String(appear);
      let html = "";
      for (let i = 0; i < group.length; i++) {
        const active = start + i === activeIdx;
        const color = active ? "#ffdf7e" : "#f3f3f3";
        html += `<span style="color:${color};text-shadow:2px 2px 0 rgba(0,0,0,0.9),0 0 5px rgba(0,0,0,0.55)">${escapeHtml(group[i].text)}</span>`;
      }
      row.innerHTML = html;
    }
    update(0);
    return { node: wrap, update };
  }

  function buildActionCaption(text) {
    const wrap = el("div", {
      position: "absolute", inset: "0", display: "flex",
      justifyContent: "flex-start", alignItems: "center", flexDirection: "column",
      paddingTop: "70px", pointerEvents: "none",
    });
    const line = el("div", {
      fontFamily: '"Arial", system-ui, sans-serif', fontStyle: "italic", fontWeight: "700",
      fontSize: "52px", color: "#fff", textAlign: "center", maxWidth: "80%",
      textShadow: "3px 3px 0 #000, -3px 3px 0 #000, 3px -3px 0 #000, -3px -3px 0 #000",
    });
    line.textContent = text;
    wrap.appendChild(line);
    return wrap;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---- Assemble: scenes as direct-child clips on one paused timeline ----
  // (<audio> elements are already static in index.html, emitted by render.mjs.)
  window.__timelines = window.__timelines || {};
  const tl = gsap.timeline({ paused: true });
  const SHOTS = window.__SHOTS || [];

  let startFrame = 0;
  M.scenes.forEach((scene, index) => {
    const durFrames = scene.durationInFrames;
    const startSec = startFrame / FPS;
    const durSec = durFrames / FPS;

    const sceneDiv = el("div", { position: "absolute", inset: "0", width: px(W), height: px(H) });
    sceneDiv.id = `scene-${index}`;
    sceneDiv.className = "clip";
    sceneDiv.setAttribute("data-start", startSec.toFixed(4));
    sceneDiv.setAttribute("data-duration", durSec.toFixed(4));
    sceneDiv.setAttribute("data-track-index", "0");

    const updaters = [];
    if (scene.kind === "transformation" && scene.panels) {
      const t = buildTransformation(scene);
      sceneDiv.appendChild(t.node);
      updaters.push(t.update);
    } else {
      const cam = buildCameraScene(scene, SHOTS[index] || []);
      sceneDiv.appendChild(cam.node);
      updaters.push(cam.update);
    }
    if (scene.caption) sceneDiv.appendChild(buildActionCaption(scene.caption));
    const caps = buildCaptions(scene.tokens);
    sceneDiv.appendChild(caps.node);
    updaters.push(caps.update);

    stage.appendChild(sceneDiv);

    // one driver tween per scene: drv.f == scene-local frame
    const drv = { f: 0 };
    tl.to(drv, {
      f: durFrames, duration: durSec, ease: "none",
      onUpdate: () => { const frame = drv.f; updaters.forEach((u) => u(frame)); },
    }, startSec);

    startFrame += durFrames;
  });

  window.__timelines[M.id] = tl;
})();
