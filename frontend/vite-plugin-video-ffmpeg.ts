/**
 * vite-plugin-video-ffmpeg
 * Custom Vite plugin that uses system ffmpeg to process video assets during build.
 *
 * Features:
 *  - Converts source videos to optimized mp4 (H.264) + webm (VP9)
 *  - colorMatch: remaps video background to exact page bg color via curves filter
 *  - vignette: darkens edges in-video for seamless page blending
 *  - extraFilters: any additional ffmpeg -vf filter string
 *  - Cache: skips re-encode when outputs are newer than input (unless force:true)
 */

import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import type { Plugin } from 'vite';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface RGB {
  r: number;
  g: number;
  b: number;
}

export interface ColorMatchOptions {
  /**
   * Sampled background color from the source video (use ffprobe or eyedropper).
   * The plugin maps this color to `targetBg` in the output.
   */
  sourceBg: RGB;
  /**
   * Target background color — typically your page/app background.
   * Shadows darker than sourceBg are mapped proportionally.
   */
  targetBg: RGB;
  /**
   * Midtone anchor strength 0–1. Lower = tighter correction, less effect on midtones.
   * Default: 0.18
   */
  midtoneAnchor?: number;
}

export interface VideoEntry {
  /** Absolute or relative path to source video (relative to project root) */
  input: string;
  /** Output filename without extension (placed in outputDir) */
  name: string;
  /** CRF for mp4 H.264 (0–51, lower = better quality; default 20) */
  crfMp4?: number;
  /** CRF for webm VP9 (0–63; default 32) */
  crfWebm?: number;
  /** Target width in px; height auto-scaled (divisible by 2). Default: source width */
  width?: number;
  /**
   * Remap video background shadows to match the page background color.
   * Computed as a per-channel curves filter; midtones and highlights are preserved.
   */
  colorMatch?: ColorMatchOptions;
  /**
   * Add a natural edge vignette (darkens corners) directly into the video.
   * Value is the vignette angle in radians (e.g. Math.PI / 4). Default off.
   */
  vignette?: number;
  /**
   * Extra ffmpeg video filter expression appended after built-in filters.
   * Example: "unsharp=5:5:0.3" to sharpen.
   */
  extraFilters?: string;
  /**
   * Force re-encode even if output already exists and is newer than input.
   * Useful when changing filter parameters. Default: false
   */
  force?: boolean;
}

export interface VideoFFmpegOptions {
  /** Directory relative to project root where optimized videos are written (default: 'public/videos') */
  outputDir?: string;
  /** Video entries to process */
  videos: VideoEntry[];
  /** Path to ffmpeg binary (default: 'ffmpeg' from PATH) */
  ffmpegPath?: string;
}

// ─── Curves builder ──────────────────────────────────────────────────────────

/**
 * Builds a per-channel curves filter string that remaps `sourceBg → targetBg`
 * while leaving midtones and highlights virtually unchanged.
 *
 * Strategy: 3-point curve per channel
 *   (0, 0)                          — black stays black
 *   (src/255, tgt/255)              — background anchor
 *   (anchor, anchor * midAdj)       — midtone barely moves (within 2%)
 *   (1, 1)                          — white stays white
 */
function buildCurvesFilter(cm: ColorMatchOptions): string {
  const { sourceBg, targetBg, midtoneAnchor = 0.18 } = cm;

  const buildChannel = (src: number, tgt: number): string => {
    const sn = +(src / 255).toFixed(4);
    const tn = +(tgt / 255).toFixed(4);
    // Midtone anchor: slightly adjusted to ease the curve smoothly
    const midIn = midtoneAnchor;
    // Interpolate midtone output so it's only slightly lower than input
    const ratio = sn > 0 ? tn / sn : 1;
    // Blend ratio toward 1.0 at midtones (effect fades out as we move away from bg)
    const midBlend = Math.min(1, sn / midIn); // 0 at black, 1 at midtone
    const midRatio = 1 - (1 - ratio) * (1 - midBlend);
    const midOut = +(midIn * midRatio).toFixed(4);
    return `'0/0 ${sn}/${tn} ${midIn}/${midOut} 1/1'`;
  };

  const r = buildChannel(sourceBg.r, targetBg.r);
  const g = buildChannel(sourceBg.g, targetBg.g);
  const b = buildChannel(sourceBg.b, targetBg.b);

  return `curves=r=${r}:g=${g}:b=${b}`;
}

// ─── Filter chain builder ─────────────────────────────────────────────────────

function buildVfChain(entry: VideoEntry): string {
  const parts: string[] = [];

  // 1. Scale (always first)
  if (entry.width) {
    parts.push(`scale=${entry.width}:-2`);
  }

  // 2. Color background matching
  if (entry.colorMatch) {
    parts.push(buildCurvesFilter(entry.colorMatch));
  }

  // 3. Edge vignette
  if (entry.vignette !== undefined) {
    parts.push(`vignette=${entry.vignette.toFixed(6)}`);
  }

  // 4. Extra user-defined filters
  if (entry.extraFilters) {
    parts.push(entry.extraFilters);
  }

  // Default: passthrough scale if nothing specified
  if (parts.length === 0) {
    parts.push('scale=iw:ih');
  }

  return parts.join(',');
}

// ─── ffmpeg runner ────────────────────────────────────────────────────────────

function runFFmpeg(args: string[], label: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const proc = spawn('ffmpeg', args, { stdio: ['ignore', 'ignore', 'pipe'] });
    let stderr = '';
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg failed for ${label}:\n${stderr.slice(-600)}`));
    });
    proc.on('error', (err) => reject(new Error(`ffmpeg spawn error: ${err.message}`)));
  });
}

// ─── Core processor ───────────────────────────────────────────────────────────

async function processVideo(
  entry: VideoEntry,
  outputDir: string,
  root: string,
): Promise<void> {
  const inputPath = path.isAbsolute(entry.input)
    ? entry.input
    : path.resolve(root, entry.input);

  if (!fs.existsSync(inputPath)) {
    console.warn(`[vite-plugin-video-ffmpeg] Source not found: ${inputPath}`);
    return;
  }

  const absOutputDir = path.isAbsolute(outputDir)
    ? outputDir
    : path.resolve(root, outputDir);

  fs.mkdirSync(absOutputDir, { recursive: true });

  const crf     = entry.crfMp4  ?? 20;
  const crfWebm = entry.crfWebm ?? 32;
  const vfChain = buildVfChain(entry);

  const mp4Out  = path.join(absOutputDir, `${entry.name}.mp4`);
  const webmOut = path.join(absOutputDir, `${entry.name}.webm`);

  const inputMtime = fs.statSync(inputPath).mtimeMs;
  const shouldSkip = (outPath: string) =>
    !entry.force &&
    fs.existsSync(outPath) &&
    fs.statSync(outPath).mtimeMs > inputMtime;

  const tasks: Promise<void>[] = [];

  if (!shouldSkip(mp4Out)) {
    console.log(`[vite-plugin-video-ffmpeg] Encoding mp4  → ${entry.name}.mp4  (vf: ${vfChain})`);
    tasks.push(
      runFFmpeg([
        '-y', '-i', inputPath,
        '-c:v', 'libx264',
        '-crf', String(crf),
        '-preset', 'slow',
        '-an',
        '-movflags', '+faststart',
        '-vf', vfChain,
        mp4Out,
      ], `${entry.name}.mp4`),
    );
  }

  if (!shouldSkip(webmOut)) {
    console.log(`[vite-plugin-video-ffmpeg] Encoding webm → ${entry.name}.webm (vf: ${vfChain})`);
    tasks.push(
      runFFmpeg([
        '-y', '-i', inputPath,
        '-c:v', 'libvpx-vp9',
        '-crf', String(crfWebm),
        '-b:v', '0',
        '-deadline', 'best',
        '-cpu-used', '0',
        '-an',
        '-vf', vfChain,
        webmOut,
      ], `${entry.name}.webm`),
    );
  }

  if (tasks.length === 0) {
    console.log(`[vite-plugin-video-ffmpeg] Up-to-date: ${entry.name} (skipped)`);
    return;
  }

  await Promise.all(tasks);
  console.log(`[vite-plugin-video-ffmpeg] Done: ${entry.name}`);
}

// ─── Plugin export ────────────────────────────────────────────────────────────

export function videoFFmpegPlugin(options: VideoFFmpegOptions): Plugin {
  let resolvedRoot: string;
  const outputDir = options.outputDir ?? 'public/videos';

  return {
    name: 'vite-plugin-video-ffmpeg',

    configResolved(config) {
      resolvedRoot = config.root;
    },

    async buildStart() {
      await Promise.all(
        options.videos.map((v) => processVideo(v, outputDir, resolvedRoot ?? process.cwd())),
      );
    },

    configureServer(server) {
      Promise.all(
        options.videos.map((v) => processVideo(v, outputDir, server.config.root)),
      ).catch(console.error);
    },
  };
}
