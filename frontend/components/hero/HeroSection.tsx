import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Mic, MicOff, Loader2 } from 'lucide-react';
import { AppSection } from '../../types';
import { useVoiceInput } from '../../src/hooks/useVoiceInput';

interface HeroSectionProps {
  onNavigate?: (section: AppSection) => void;
  onSubmit?: (query: string) => void;
}

const DEFAULT_SUGGESTIONS = [
  'Co nowego w Rybnie?',
  'Jakie są awarie w gminie?',
  'Kiedy odbiór śmieci?',
  'Co robić w weekend?',
  'Jakie są nadchodzące wydarzenia?',
  'Ile osób mieszka w gminie?',
  'Jakie są dochody gminy?',
  'Co mówi BIP o przetargach?',
];

const BG = '#05080f';
const TOTAL_FRAMES  = 121;
// Zoom in slightly so the image overflows the canvas horizontally,
// giving room to pan left/right via objectPositionX.
// 1.08 creates ~8% horizontal overflow on 16:9 monitors, enough to pan left.
// Keep small so ball doesn't zoom too aggressively.
const SCALE_BOOST   = 1.08;

const HeroSection: React.FC<HeroSectionProps> = ({ onNavigate, onSubmit }) => {
  const [query, setQuery]                         = useState('');
  const [suggestions, setSuggestions]             = useState<string[]>(DEFAULT_SUGGESTIONS);
  const [currentSuggestion, setCurrentSuggestion] = useState(0);
  const [isTyping, setIsTyping]                   = useState(false);
  const [inputFocused, setInputFocused]           = useState(false);
  const speech = useVoiceInput((text) => {
    setQuery(text);
    setIsTyping(true);
  });

  const containerRef    = useRef<HTMLDivElement>(null);
  const canvasRef       = useRef<HTMLCanvasElement>(null);
  const framesRef       = useRef<HTMLImageElement[]>([]);
  const progressRef     = useRef(0);
  const currentFrameRef = useRef(0);

  // ── suggestions ──────────────────────────────────────────────────────────
  useEffect(() => {
    fetch('/api/chat/suggestions')
      .then(r => r.json())
      .then(d => { if (d.suggestions?.length) setSuggestions(d.suggestions); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (isTyping) return;
    const id = setInterval(
      () => setCurrentSuggestion(i => (i + 1) % suggestions.length),
      3000,
    );
    return () => clearInterval(id);
  }, [suggestions.length, isTyping]);

  // ── canvas draw — cover behaviour matching objectPosition: 40% 55% ───────
  const drawFrame = useCallback((idx: number) => {
    const canvas = canvasRef.current;
    const ctx    = canvas?.getContext('2d');
    const img    = framesRef.current[idx];
    if (!canvas || !ctx || !img?.complete || !img.naturalWidth) return;

    const cw = canvas.width;
    const ch = canvas.height;
    const iw = img.naturalWidth;   // 1280
    const ih = img.naturalHeight;  // 720

    // cover + slight zoom so there's horizontal overflow room for panning
    const scale = Math.max(cw / iw, ch / ih) * SCALE_BOOST;
    const dw    = iw * scale;
    const dh    = ih * scale;

    // On mobile (<1024px): centre the ball (dxFactor=0.50).
    // On desktop: shift slightly left (dxFactor=0.62).
    const isMobile  = cw < 1024;
    const dxFactor  = isMobile ? 0.50 : 0.62;
    const dyFactor  = isMobile ? 0.48 : 0.55;
    const dx = (cw - dw) * dxFactor;
    const dy = (ch - dh) * dyFactor;

    ctx.clearRect(0, 0, cw, ch);
    ctx.drawImage(img, dx, dy, dw, dh);
    currentFrameRef.current = idx;
  }, []);

  // ── preload all frames ────────────────────────────────────────────────────
  useEffect(() => {
    const imgs: HTMLImageElement[] = [];
    for (let i = 0; i < TOTAL_FRAMES; i++) {
      const img = new Image();
      img.src   = `/videos/kula6/${String(i + 1).padStart(4, '0')}.jpg`;
      imgs.push(img);
    }
    framesRef.current = imgs;

    // Draw frame 0 as soon as it's decoded
    const drawFirst = () => drawFrame(0);
    imgs[0].onload = drawFirst;
    if (imgs[0].complete) drawFirst();
  }, [drawFrame]);

  // ── sync canvas pixel size to CSS size (ResizeObserver) ──────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const sync = () => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      if (w === 0 || h === 0) return;
      canvas.width  = w;
      canvas.height = h;
      drawFrame(currentFrameRef.current);
    };

    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(canvas);
    return () => ro.disconnect();
  }, [drawFrame]);

  // ── scroll → frame scrubbing ──────────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let rafId: number | null = null;

    const scrub = () => {
      const progress = Math.min(1, Math.max(0, window.scrollY / (container.offsetHeight * 0.75)));
      progressRef.current = progress;
      // clamp to valid index
      const frameIdx = Math.min(TOTAL_FRAMES - 1, Math.floor(progress * TOTAL_FRAMES));
      drawFrame(frameIdx);
      rafId = null;
    };

    const onScroll = () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(scrub);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, [drawFrame]);

  const handleSubmit = (text: string) => {
    if (!text.trim()) return;
    onSubmit?.(text);
    onNavigate?.('assistant');
  };

  return (
    <div
      ref={containerRef}
      className="relative w-full flex items-center"
      style={{ minHeight: 'clamp(560px, 90vh, 920px)' }}
    >

      {/* ── CANVAS BACKGROUND — frame-sequence scroll animation ───────────── */}
      {/*
        Technique: 121 JPG frames pre-loaded into HTMLImageElement[].
        Scroll maps linearly to frame index → ctx.drawImage() per RAF tick.
        Canvas is faster than video.currentTime scrubbing because:
          - No seek latency / decoder stall
          - Direct GPU-backed 2D blit
          - No audio track overhead
        CSS mask fades edges; gradient divs cover the BG colour seam.
      */}
      {/* Canvas wrapper extended 120px above the hero container so the ball's
          glow bleeds through the Dashboard header (RybnoLive / Witaj) area.
          Dashboard header has z-[70] so it stays on top of this canvas (z:0). */}
      <div
        aria-hidden
        style={{
          position:        'absolute',
          top:             '-120px',
          left:            '50%',
          transform:       'translateX(-50%)',
          width:           '100vw',
          height:          'calc(110% + 120px)',
          zIndex:          0,
          pointerEvents:   'none',
          // top 8% fade covers the 120px extension + a bit of hero top
          maskImage:       'linear-gradient(to bottom, transparent 0%, black 8%, black 85%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 8%, black 85%, transparent 100%)',
        }}
      >
        <canvas
          ref={canvasRef}
          style={{
            display: 'block',
            width:   '100%',
            height:  '100%',
          }}
        />

        {/* Right: dark ramp for text legibility */}
        <div style={{
          position:      'absolute',
          inset:         '0 0 0 auto',
          width:         '45%',
          background:    `linear-gradient(to left, ${BG} 0%, ${BG}e6 28%, ${BG}66 60%, transparent 100%)`,
          pointerEvents: 'none',
        }} />

        {/* Bottom: merges into card section */}
        <div style={{
          position:      'absolute',
          inset:         'auto 0 0 0',
          height:        '14rem',
          background:    `linear-gradient(to top, ${BG} 0%, ${BG}e6 45%, transparent 100%)`,
          pointerEvents: 'none',
        }} />
      </div>

      {/* ── CONTENT ──────────────────────────────────────────────────────── */}
      {/* mobile: centre over the centred ball; lg: push right over ball-left layout */}
      <div className="relative z-10 w-full flex justify-center lg:justify-end px-6 lg:px-8">
        <div className="w-full max-w-2xl lg:pr-14 py-12 lg:py-24 text-center lg:text-left">

          {/* Status pill */}
          <div
            className="inline-flex items-center gap-2 rounded-full mb-6 text-xs tracking-widest uppercase"
            style={{
              padding:              '5px 16px',
              background:           'rgba(255,255,255,0.06)',
              border:               '1px solid rgba(255,255,255,0.1)',
              color:                'var(--chart-1)',
              fontFamily:           'var(--font-mono, monospace)',
              backdropFilter:       'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
            }}
          >
            <span className="relative flex h-2 w-2 flex-shrink-0">
              <span
                className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                style={{ background: 'var(--chart-2)' }}
              />
              <span
                className="relative inline-flex rounded-full h-2 w-2"
                style={{ background: 'var(--chart-2)' }}
              />
            </span>
            5 agentów AI aktywnych
          </div>

          {/* H1 */}
          <h1
            className="font-extrabold leading-[1.05] mb-6 tracking-tight"
            style={{ fontSize: 'clamp(44px, 5.5vw, 88px)' }}
          >
            <span className="text-white drop-shadow-xl">
              Centrum
              <br />
              Operacyjne
              <br />
            </span>
            <span style={{ color: '#5b9cf6', filter: 'drop-shadow(0 0 20px rgba(91,156,246,0.35))' }}>
              Rybna
            </span>
          </h1>

          <p
            className="mb-10 leading-relaxed font-medium"
            style={{ fontSize: 'clamp(15px, 1.1vw, 18px)', color: 'var(--muted-foreground)', maxWidth: '32rem' }}
          >
            Zapytaj o wiadomości, urząd, statystyki lub wydarzenia gminy Rybno
          </p>

          <p className="font-semibold mb-3 text-white" style={{ fontSize: 'clamp(16px, 1.3vw, 20px)' }}>
            W czym mogę pomóc?
          </p>

          <div className="flex gap-2 mb-5">
            <input
              type="text"
              value={query}
              onChange={e => { setQuery(e.target.value); setIsTyping(true); }}
              onFocus={() => setInputFocused(true)}
              onBlur={() => { setInputFocused(false); setIsTyping(false); }}
              onKeyDown={e => e.key === 'Enter' && handleSubmit(query)}
              placeholder={speech.isListening ? 'Słucham...' : suggestions[currentSuggestion]}
              className="flex-1 rounded-2xl px-6 py-4 text-base transition-all"
              style={{
                background:           'rgba(21,27,43,0.8)',
                backdropFilter:       'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                border:               `1px solid ${
                  speech.isListening ? 'rgba(239,68,68,0.6)'
                  : inputFocused ? 'var(--chart-2)'
                  : 'rgba(255,255,255,0.12)'
                }`,
                boxShadow:            inputFocused || speech.isListening
                  ? '0 0 0 3px rgba(58,129,246,0.18), 0 4px 20px rgba(0,0,0,0.4)'
                  : '0 4px 20px rgba(0,0,0,0.4)',
                color:                '#fafafa',
                outline:              'none',
                fontFamily:           'inherit',
                caretColor:           'var(--chart-1)',
              }}
            />
            {speech.isSupported && (
              <button
                onClick={() => speech.isListening ? speech.stop() : speech.start()}
                disabled={speech.isProcessing}
                title={
                  speech.error === 'not-allowed'
                    ? 'Zezwól na mikrofon w ustawieniach przeglądarki'
                    : speech.isProcessing ? 'Przetwarzam nagranie...'
                    : speech.isListening ? 'Zatrzymaj nagrywanie'
                    : 'Mów do mikrofonu'
                }
                className="shrink-0 flex items-center justify-center rounded-2xl px-4 transition-all"
                style={{
                  background: speech.isProcessing
                    ? 'rgba(59,130,246,0.15)'
                    : speech.isListening
                    ? 'rgba(239,68,68,0.15)'
                    : speech.error === 'not-allowed'
                    ? 'rgba(245,158,11,0.1)'
                    : 'rgba(21,27,43,0.8)',
                  border: `1px solid ${
                    speech.isProcessing ? 'rgba(59,130,246,0.5)'
                    : speech.isListening ? 'rgba(239,68,68,0.5)'
                    : speech.error === 'not-allowed' ? 'rgba(245,158,11,0.4)'
                    : 'rgba(255,255,255,0.12)'
                  }`,
                  color: speech.isProcessing ? '#60a5fa'
                    : speech.isListening ? '#f87171'
                    : speech.error === 'not-allowed' ? '#fbbf24'
                    : 'rgba(255,255,255,0.5)',
                  backdropFilter: 'blur(12px)',
                }}
              >
                {speech.isProcessing
                  ? <Loader2 size={18} className="animate-spin" />
                  : speech.isListening
                  ? <MicOff size={18} />
                  : <Mic size={18} />}
              </button>
            )}
            <button
              onClick={() => handleSubmit(query || suggestions[currentSuggestion])}
              className="btn-primary shrink-0 flex items-center gap-2"
            >
              <Send size={15} />
              <span className="hidden sm:inline">Zapytaj</span>
            </button>
          </div>

          <div className="flex flex-wrap gap-2 justify-center lg:justify-start">
            {suggestions.slice(0, 4).map((s, i) => (
              <button key={i} onClick={() => handleSubmit(s)} className="btn-chip">
                {s}
              </button>
            ))}
          </div>

        </div>
      </div>
    </div>
  );
};

export default HeroSection;
