import { cn } from "../../lib/utils";

interface BeamsBackgroundProps {
  className?: string;
  intensity?: "subtle" | "medium" | "strong";
}

// Opacity scale per intensity — blobs stay very subtle so they don't fight content
const intensityOpacity = { subtle: 0.12, medium: 0.18, strong: 0.24 };

/**
 * AuroraBackground — replaces canvas BeamsBackground.
 * Three slowly drifting radial-gradient blobs rendered as pure CSS divs.
 *
 * Performance: ~0% CPU. Each blob is a GPU-composited layer whose transform
 * matrix is animated by the compositor thread. No canvas, no JS loop, no blur
 * recalculated per-frame. The @keyframes are defined in index.html.
 */
export function BeamsBackground({ className, intensity = "medium" }: BeamsBackgroundProps) {
  const opacity = intensityOpacity[intensity];

  return (
    <div className={cn("inset-0 overflow-hidden pointer-events-none", className)}>

      {/* Blob 1 — Blue, top-center-left, 28s */}
      <div
        className="aurora-blob absolute rounded-full"
        style={{
          top: "-15%",
          left: "15%",
          width: "52vw",
          height: "52vw",
          background: `radial-gradient(circle, rgba(37,99,235,${opacity}) 0%, transparent 65%)`,
          filter: "blur(90px)",
          willChange: "transform",
          animation: "aurora-1 28s ease-in-out infinite",
        }}
      />

      {/* Blob 2 — Cyan, bottom-right, 36s reverse feel */}
      <div
        className="aurora-blob absolute rounded-full"
        style={{
          bottom: "0%",
          right: "5%",
          width: "46vw",
          height: "46vw",
          background: `radial-gradient(circle, rgba(6,182,212,${opacity * 0.85}) 0%, transparent 65%)`,
          filter: "blur(100px)",
          willChange: "transform",
          animation: "aurora-2 36s ease-in-out infinite",
        }}
      />

      {/* Blob 3 — Indigo, mid-left, 22s */}
      <div
        className="aurora-blob absolute rounded-full"
        style={{
          top: "35%",
          left: "-8%",
          width: "38vw",
          height: "38vw",
          background: `radial-gradient(circle, rgba(99,102,241,${opacity * 0.75}) 0%, transparent 65%)`,
          filter: "blur(80px)",
          willChange: "transform",
          animation: "aurora-3 22s ease-in-out infinite",
        }}
      />
    </div>
  );
}
