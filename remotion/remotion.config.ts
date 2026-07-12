import { Config } from "@remotion/cli/config";

// Wojak-style cat stories render config.
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// ANGLE gives reliable image/video compositing on macOS headless Chrome.
Config.setChromiumOpenGlRenderer("angle");
