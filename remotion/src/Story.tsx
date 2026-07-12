import { AbsoluteFill, Audio, Series } from "remotion";
import { asset, dbToLin } from "./assets";
import { Scene } from "./Scene";
import type { Manifest } from "./schema";

export const Story: React.FC<Manifest> = (m) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {m.music ? (
        <Audio loop src={asset(m.assetsBase, m.music.src)} volume={dbToLin(m.music.gainDb)} />
      ) : null}
      <Series>
        {m.scenes.map((s, i) => (
          <Series.Sequence key={s.id} durationInFrames={s.durationInFrames}>
            <Scene scene={s} assetsBase={m.assetsBase} index={i} />
          </Series.Sequence>
        ))}
      </Series>
    </AbsoluteFill>
  );
};
