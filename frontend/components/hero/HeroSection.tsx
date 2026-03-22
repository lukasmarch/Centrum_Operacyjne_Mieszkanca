import React, { useState, useEffect } from 'react';
import { Send } from 'lucide-react';
import { SplineScene } from '../ui/spline-scene';
import { Spotlight } from '../ui/spotlight';
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
    <div className="relative w-full rounded-3xl border border-gray-800/40 overflow-hidden min-h-[420px] lg:min-h-[460px]">

      {/* === SPLINE jako pełne tło === */}
      <div className="absolute inset-0 w-full h-full">
        <SplineScene
          scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
          className="w-full h-full"
        />
      </div>

      {/* Gradient overlay: lewo przezroczyste → prawo ciemne (dla czytelności tekstu) */}
      <div className="absolute inset-0 bg-gradient-to-r from-black/10 via-black/30 to-black/85 pointer-events-none" />

      {/* Gradient dół - delikatne zaciemnienie dolnej krawędzi */}
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/60 to-transparent pointer-events-none" />

      {/* Spotlight effect */}
      <Spotlight
        className="-top-40 left-0 md:left-20 md:-top-20"
        fill="white"
      />

      {/* === CONTENT na wierzchu === */}
      <div className="relative z-10 flex items-center justify-end h-full min-h-[420px] lg:min-h-[460px] px-6 py-8 lg:px-12">
        <div className="w-full max-w-md lg:max-w-lg">

          {/* Status pill */}
          <div className="inline-flex items-center gap-2 bg-black/50 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs text-neutral-300 mb-6">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
            </span>
            5 agentów AI aktywnych
          </div>

          {/* Heading */}
          <h2
            className="text-3xl lg:text-4xl xl:text-5xl font-bold mb-2 leading-tight"
            style={{
              background: 'linear-gradient(to bottom, #ffffff, #ffffff, rgba(255,255,255,0.6))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              letterSpacing: '-0.03em',
            }}
          >
            W czym mogę pomóc?
          </h2>
          <p className="text-neutral-400 text-sm mb-6">
            Zapytaj o wiadomości, urząd, statystyki lub wydarzenia
          </p>

          {/* Search input */}
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={query}
              onChange={e => { setQuery(e.target.value); setIsTyping(true); }}
              onBlur={() => setIsTyping(false)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit(query)}
              placeholder={suggestions[currentSuggestion]}
              className="flex-1 bg-black/50 backdrop-blur-md border border-white/10 rounded-2xl px-5 py-3 text-white placeholder-neutral-600 focus:outline-none focus:border-white/30 focus:bg-black/60 transition-all text-sm"
            />
            <button
              onClick={() => handleSubmit(query || suggestions[currentSuggestion])}
              className="shrink-0 bg-white text-black rounded-2xl px-5 py-3 font-bold transition-all hover:bg-white/90 hover:scale-105 active:scale-95 flex items-center gap-2 text-sm shadow-lg"
            >
              <Send size={14} />
              <span className="hidden sm:inline">Zapytaj</span>
            </button>
          </div>

          {/* Quick suggestion chips */}
          <div className="flex flex-wrap gap-2">
            {suggestions.slice(0, 4).map((s, i) => (
              <button
                key={i}
                onClick={() => handleSubmit(s)}
                className="text-xs text-neutral-400 bg-black/40 backdrop-blur-sm border border-white/10 hover:border-white/30 hover:text-white px-3 py-1.5 rounded-full transition-all"
              >
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
