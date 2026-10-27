use ff_debate::{DebateVideo, HEIGHT, WIDTH};
use fframes::cli::clap; // the derive below expands to `clap::...`
use fframes::{EncoderOptions, MediaDirectory, RenderOptions, cli};
use fframes_skia_renderer::{
    SkiaFFramesRenderer, SkiaPipelineConcurrencyPolicy, SkiaPipelineConfig, metal::SkiaMetalCtx,
};
use std::path::PathBuf;
use std::process::ExitCode;

/// The episode to draw: the media folder `engine/news_render.py` prepares
/// (work/news/<slug>/media, with timeline.json, the tracks, cctv.mp4 and audio.wav).
/// Given as `--work <dir>` or the `FF_WORK` environment variable.
#[derive(Debug, clap::Args)]
struct VideoArgs {
    #[arg(long, global = true)]
    work: Option<PathBuf>,
}

fn main() -> ExitCode {
    let args = cli::parse::<VideoArgs>();
    let work = args.app.work.clone()
        .or_else(|| std::env::var_os("FF_WORK").map(PathBuf::from))
        .expect("pass --work <dir> or set FF_WORK");
    let json = std::fs::read_to_string(work.join("timeline.json")).expect("timeline.json in --work");
    let video = DebateVideo::from_json(&json).expect("valid timeline.json");
    let directory = MediaDirectory::read_folder(&work).expect("media folder");
    let media = directory.process_media_source().expect("media");
    let gpu = SkiaMetalCtx::new(WIDTH, HEIGHT).expect("GPU context");

    cli::new(
        &video,
        RenderOptions {
            media: Some(&media),
            // Impact, Arial and Menlo come from the system (macOS), not the repo.
            load_system_fonts: true,
            default_font: "Arial",
            video_encoder_options: EncoderOptions {
                preferred_encoder: Some("libx264"),
                codec_params: Some(&[("crf", "17"), ("preset", "medium")]),
                ..Default::default()
            },
            ..Default::default()
        },
    )
    .args(args)
    .backend(
        SkiaFFramesRenderer::new_metal(
            &gpu,
            SkiaPipelineConfig {
                concurrency_policy: SkiaPipelineConcurrencyPolicy::MaxPerformance,
                ..Default::default()
            },
        )
        .expect("skia renderer"),
    )
    .preview(fframes_native_player::cli_preview)
    .run()
}
