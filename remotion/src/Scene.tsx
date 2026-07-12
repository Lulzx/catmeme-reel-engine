import { AbsoluteFill, Audio } from "remotion";
import { asset } from "./assets";
import { Background } from "./Background";
import { Character } from "./Character";
import { Camera } from "./Camera";
import { Captions, ActionCaption } from "./Captions";
import { Transformation } from "./Transformation";
import type { SceneT } from "./schema";

export const Scene: React.FC<{ scene: SceneT; assetsBase: string; index: number }> = ({
  scene,
  assetsBase,
  index,
}) => {
  // Frame the camera on the (first) cat so close-ups land on its face.
  const focus = scene.characters?.[0]?.rect;
  return (
    <AbsoluteFill>
      {scene.kind === "transformation" && scene.panels ? (
        <Transformation panels={scene.panels} assetsBase={assetsBase} />
      ) : (
        <Camera rect={focus} seed={index} sceneDur={scene.durationInFrames}>
          <Background bg={scene.background} assetsBase={assetsBase} />
          {scene.characters.map((ch, i) => (
            <Character key={`${ch.id}-${i}`} ch={ch} assetsBase={assetsBase} />
          ))}
        </Camera>
      )}
      {scene.caption ? <ActionCaption text={scene.caption} /> : null}
      <Captions tokens={scene.tokens} />
      {scene.audio ? <Audio src={asset(assetsBase, scene.audio)} /> : null}
    </AbsoluteFill>
  );
};
