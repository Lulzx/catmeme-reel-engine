import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Background } from "./Background";
import { Character } from "./Character";
import type { PanelT } from "./schema";

const PANEL_LABEL_FONT = '"Arial Black", Impact, system-ui, sans-serif';

const Panel: React.FC<{ panel: PanelT; assetsBase: string; side: "left" | "right" }> = ({
  panel,
  assetsBase,
  side,
}) => (
  <AbsoluteFill
    style={{ clipPath: side === "left" ? "inset(0 50% 0 0)" : "inset(0 0 0 50%)" }}
  >
    <Background bg={panel.background} assetsBase={assetsBase} />
    <Character ch={panel.character} assetsBase={assetsBase} />
    {panel.label ? (
      <div
        style={{
          position: "absolute",
          top: 54,
          left: side === "left" ? 0 : "50%",
          width: "50%",
          textAlign: "center",
          fontFamily: PANEL_LABEL_FONT,
          fontSize: 58,
          color: "#fff",
          letterSpacing: 2,
          textShadow: "3px 3px 0 #000, -3px 3px 0 #000, 3px -3px 0 #000, -3px -3px 0 #000",
        }}
      >
        {panel.label}
      </div>
    ) : null}
  </AbsoluteFill>
);

const RedArrow: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 11, stiffness: 130, mass: 0.7 } });
  const scale = 0.4 + 0.6 * p;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <svg
        width="360"
        height="200"
        viewBox="0 0 360 200"
        style={{ transform: `scale(${scale})`, filter: "drop-shadow(0 6px 10px rgba(0,0,0,0.5))" }}
      >
        <path
          d="M30 120 C 120 40, 230 40, 300 95 L 300 60 L 350 110 L 300 160 L 300 125 C 230 80, 130 80, 55 150 Z"
          fill="#ff2b2b"
          stroke="#fff"
          strokeWidth="6"
          strokeLinejoin="round"
        />
      </svg>
    </AbsoluteFill>
  );
};

export const Transformation: React.FC<{ panels: PanelT[]; assetsBase: string }> = ({
  panels,
  assetsBase,
}) => {
  const [before, after] = panels;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {before ? <Panel panel={before} assetsBase={assetsBase} side="left" /> : null}
      {after ? <Panel panel={after} assetsBase={assetsBase} side="right" /> : null}
      {/* center seam */}
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ width: 6, height: "100%", background: "rgba(255,255,255,0.85)" }} />
      </AbsoluteFill>
      <RedArrow />
    </AbsoluteFill>
  );
};
