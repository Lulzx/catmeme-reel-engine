import { z } from "zod";

export const rectSchema = z.object({
  x: z.number(),
  y: z.number(),
  width: z.number(),
  height: z.number(),
});

export const tokenSchema = z.object({
  text: z.string(),
  startMs: z.number(),
  endMs: z.number(),
});

/** Resolved color grade (Python computes from a mood name; Remotion applies as CSS). */
export const gradeSchema = z.object({
  filter: z.string().default("none"), // applied to the bg image
  tint: z.string().default("#000000"),
  tintOpacity: z.number().default(0),
  blend: z.string().default("normal"), // CSS mix-blend-mode
  vignette: z.number().default(0.3),
});

export const characterSchema = z.object({
  id: z.string(),
  kind: z.enum(["sprite", "animated"]),
  src: z.string(),
  seqCount: z.number().optional(),
  seqFps: z.number().optional(),
  rect: rectSchema,
  flip: z.boolean().default(false),
  enter: z.enum(["slideLeft", "slideRight", "pop", "bounce", "none"]).default("pop"),
  filter: z.string().optional(), // tint cutout to the scene light
  label: z.string().optional(),
});

export const backgroundSchema = z.object({
  kind: z.enum(["flat", "themed"]),
  color: z.string().optional(),
  color2: z.string().optional(),
  src: z.string().optional(),
  grade: gradeSchema.optional(),
});

/** One half of a before/after transformation scene. */
export const panelSchema = z.object({
  label: z.string().optional(), // "BEFORE" / "AFTER"
  background: backgroundSchema,
  character: characterSchema,
});

export const sceneSchema = z.object({
  id: z.string(),
  kind: z.enum(["scene", "transformation"]).default("scene"),
  durationInFrames: z.number(),
  audio: z.string().optional(),
  background: backgroundSchema,
  caption: z.string().optional(),
  characters: z.array(characterSchema).default([]),
  panels: z.array(panelSchema).optional(), // transformation: [before, after]
  tokens: z.array(tokenSchema).default([]),
  transition: z.enum(["none", "fade", "slide"]).default("fade"),
});

export const manifestSchema = z.object({
  id: z.string(),
  fps: z.number().default(30),
  width: z.number().default(1920),
  height: z.number().default(1080),
  assetsBase: z.string().default(""),
  music: z.object({ src: z.string(), gainDb: z.number().default(-22) }).optional(),
  scenes: z.array(sceneSchema),
});

export type Manifest = z.infer<typeof manifestSchema>;
export type SceneT = z.infer<typeof sceneSchema>;
export type CharacterT = z.infer<typeof characterSchema>;
export type BackgroundT = z.infer<typeof backgroundSchema>;
export type PanelT = z.infer<typeof panelSchema>;
export type TokenT = z.infer<typeof tokenSchema>;
export type GradeT = z.infer<typeof gradeSchema>;
