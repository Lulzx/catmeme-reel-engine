import { AbsoluteFill, Img } from "remotion";
import { asset } from "./assets";
import type { BackgroundT, GradeT } from "./schema";

const Vignette: React.FC<{ amount: number }> = ({ amount }) =>
  amount > 0 ? (
    <AbsoluteFill
      style={{
        background: `radial-gradient(120% 95% at 50% 42%, rgba(0,0,0,0) 38%, rgba(0,0,0,${amount}) 100%)`,
      }}
    />
  ) : null;

const Tint: React.FC<{ grade: GradeT }> = ({ grade }) =>
  grade.tintOpacity > 0 ? (
    <AbsoluteFill
      style={{
        backgroundColor: grade.tint,
        opacity: grade.tintOpacity,
        mixBlendMode: grade.blend as React.CSSProperties["mixBlendMode"],
      }}
    />
  ) : null;

export const Background: React.FC<{ bg: BackgroundT; assetsBase: string }> = ({
  bg,
  assetsBase,
}) => {
  // The Camera component now owns all motion (push-ins, cuts, pans). The
  // background must stay a static, full-frame layer so the cat stays locked to
  // it as the camera moves the whole world together.
  const grade = bg.grade;
  if (bg.kind === "flat") {
    const c1 = bg.color ?? "#2b2b3a";
    const background = bg.color2
      ? `linear-gradient(180deg, ${c1} 0%, ${bg.color2} 100%)`
      : c1;
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ background }} />
        {grade ? <Tint grade={grade} /> : null}
        <Vignette amount={grade?.vignette ?? 0.3} />
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill>
      <Img
        src={asset(assetsBase, bg.src ?? "")}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          // A touch of defocus separates the (sharp) cat from the room — subject
          // pop, the way a shallow depth of field reads in real footage.
          filter: `${grade?.filter && grade.filter !== "none" ? grade.filter + " " : ""}blur(2.4px)`,
        }}
      />
      {grade ? <Tint grade={grade} /> : null}
      <Vignette amount={grade?.vignette ?? 0.35} />
    </AbsoluteFill>
  );
};
