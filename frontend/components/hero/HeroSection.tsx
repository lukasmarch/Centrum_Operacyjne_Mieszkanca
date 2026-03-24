import React, { useState, useEffect } from 'react';
import { Send } from 'lucide-react';
import { SplineScene } from '../ui/spline-scene';
import { AppSection } from '../../types';

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

const HeroSection: React.FC<HeroSectionProps> = ({ onNavigate, onSubmit }) => {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS);
  const [currentSuggestion, setCurrentSuggestion] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);

  useEffect(() => {
    fetch('/api/chat/suggestions')
      .then(r => r.json())
      .then(data => { if (data.suggestions?.length) setSuggestions(data.suggestions); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (isTyping) return;
    const interval = setInterval(() => {
      setCurrentSuggestion(i => (i + 1) % suggestions.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [suggestions.length, isTyping]);

  const handleSubmit = (text: string) => {
    if (!text.trim()) return;
    onSubmit?.(text);
    onNavigate?.('assistant');
  };

  return (
    <div
      className="relative overflow-visible"
      style={{ minHeight: 'clamp(560px, 72vh, 860px)', background: 'transparent' }}
    >
      {/* No local background — global BeamsBackground in App.tsx covers the whole page seamlessly */}

      {/* Two columns */}
      <div
        className="relative flex flex-col lg:flex-row"
        style={{ minHeight: 'clamp(560px, 72vh, 860px)', zIndex: 10 }}
      >

        {/* ── LEFT COLUMN: SplineScene (AI agent) ── */}
        <div
          className="relative flex-shrink-0 w-full h-[450px] lg:h-auto lg:w-[55%] z-10 pointer-events-none"
        >
          {/* 
            Agent canvas is expanded to 140% and scaled down to give the 3D model more inner padding so hands aren't clipped by canvas bounds.
            A linear-gradient mask fades the bottom so it blends seamlessly into the void. Positioned slightly left (left-[45%]).
          */}
          <div 
            className="absolute top-1/2 left-[45%] -translate-x-1/2 -translate-y-1/2 w-[140%] h-[140%] scale-[0.7] pointer-events-auto"
            style={{
              WebkitMaskImage: 'linear-gradient(to bottom, rgba(0,0,0,1) 65%, rgba(0,0,0,0) 100%)',
              maskImage: 'linear-gradient(to bottom, rgba(0,0,0,1) 65%, rgba(0,0,0,0) 100%)'
            }}
          >
            <SplineScene
              scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
              className="w-full h-full object-contain outline-none border-none bg-transparent"
            />
          </div>
        </div>

        {/* ── RIGHT COLUMN: Content (Text & Search) ── */}
        <div
          className="relative flex-1 flex items-center justify-center lg:justify-start py-8 lg:py-12 px-6 lg:px-0 lg:pr-14"
          style={{ pointerEvents: 'all', zIndex: 20 }}
        >
          <div className="w-full max-w-[480px]">

            {/* Status pill */}
            <div className="inline-flex items-center gap-2 rounded-full mb-6 text-xs tracking-widest uppercase"
              style={{
                padding: '5px 16px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'var(--chart-1)',
                fontFamily: 'var(--font-mono, monospace)',
              }}
            >
              <span className="relative flex h-2 w-2 flex-shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                  style={{ background: 'var(--chart-2)' }} />
                <span className="relative inline-flex rounded-full h-2 w-2"
                  style={{ background: 'var(--chart-2)' }} />
              </span>
              5 agentów AI aktywnych
            </div>

            {/* H1 heading */}
            <h1
              className="font-black leading-[1.04] mb-3"
              style={{ fontSize: 'clamp(44px, 4.8vw, 72px)', letterSpacing: '-0.03em', color: '#fafafa' }}
            >
              Centrum
              <br />
              Operacyjne
              <br />
              <span className="text-gradient">Rybna</span>
            </h1>

            <p className="mb-6 leading-relaxed text-sm" style={{ color: 'var(--muted-foreground)' }}>
              Zapytaj o wiadomości, urząd, statystyki lub wydarzenia gminy Rybno
            </p>

            {/* "W czym mogę pomóc" – above search */}
            <p
              className="font-semibold mb-2"
              style={{ fontSize: 'clamp(16px, 1.4vw, 20px)', color: 'var(--chart-1)' }}
            >
              W czym mogę pomóc?
            </p>

            {/* Search input row */}
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                value={query}
                onChange={e => { setQuery(e.target.value); setIsTyping(true); }}
                onFocus={() => setInputFocused(true)}
                onBlur={() => { setInputFocused(false); setIsTyping(false); }}
                onKeyDown={e => e.key === 'Enter' && handleSubmit(query)}
                placeholder={suggestions[currentSuggestion]}
                className="flex-1 rounded-xl px-5 py-3 text-sm transition-all"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: `1px solid ${inputFocused ? 'var(--chart-2)' : 'rgba(255,255,255,0.1)'}`,
                  boxShadow: inputFocused ? '0 0 0 3px rgba(58,129,246,0.15)' : 'none',
                  color: '#fafafa',
                  outline: 'none',
                  fontFamily: 'inherit',
                  caretColor: 'var(--chart-1)',
                }}
              />
              <button
                onClick={() => handleSubmit(query || suggestions[currentSuggestion])}
                className="btn-primary shrink-0 flex items-center gap-2"
              >
                <Send size={14} />
                <span className="hidden sm:inline">Zapytaj</span>
              </button>
            </div>

            {/* Suggestion chips */}
            <div className="flex flex-wrap gap-2">
              {suggestions.slice(0, 4).map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSubmit(s)}
                  className="btn-chip"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HeroSection;
