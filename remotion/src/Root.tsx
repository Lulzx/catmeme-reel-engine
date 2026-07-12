import { Composition } from "remotion";
import { Story } from "./Story";
import { manifestSchema, type Manifest } from "./schema";
import spike from "./spike-manifest.json";

const totalFrames = (m: Manifest) =>
  Math.max(1, m.scenes.reduce((a, s) => a + s.durationInFrames, 0));

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Story"
      component={Story}
      schema={manifestSchema}
      defaultProps={spike as unknown as Manifest}
      calculateMetadata={({ props }) => ({
        durationInFrames: totalFrames(props),
        fps: props.fps,
        width: props.width,
        height: props.height,
      })}
    />
  );
};
