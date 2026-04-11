import React, { useState, useEffect } from 'react';
import { Bot, Send } from 'lucide-react';
import { AppSection } from '../types';
import { useVoiceInput } from '../src/hooks/useVoiceInput';
import { VoiceMicButton } from './VoiceMicButton';

interface PromptBarProps {
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

const PromptBar: React.FC<PromptBarProps> = ({ onNavigate, onSubmit }) => {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS);
  const [currentSuggestion, setCurrentSuggestion] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const speech = useVoiceInput((text) => {
    setQuery(text);
    setIsTyping(true);
  });

  const toggleListening = () => {
    if (speech.isListening) { speech.stop(); return; }
    speech.clearError();
    speech.start();
  };

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
    <div className="relative rounded-3xl p-[1px] bg-gradient-to-br from-blue-500/40 via-indigo-500/20 to-purple-500/40 shadow-2xl shadow-blue-900/20">
      <div className="bg-slate-950/95 rounded-[23px] p-6 md:p-7 backdrop-blur-xl">

        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-500/30 shrink-0">
            <Bot size={20} className="text-white" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white leading-none">W czym mogę pomóc?</h2>
            <p className="text-xs text-slate-400 mt-0.5">Zapytaj o wiadomości, urząd, statystyki lub wydarzenia</p>
          </div>
          <div className="ml-auto hidden sm:flex items-center gap-1.5 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            5 agentów aktywnych
          </div>
        </div>

        {/* Input row */}
        <div className="flex gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              value={query}
              onChange={e => { setQuery(e.target.value); setIsTyping(true); }}
              onBlur={() => setIsTyping(false)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit(query)}
              placeholder={
                speech.isProcessing ? 'Przetwarzam nagranie...'
                : speech.isListening ? 'Słucham...'
                : suggestions[currentSuggestion]
              }
              className={`w-full bg-slate-900/80 border rounded-2xl px-5 py-3 text-slate-100 placeholder-slate-600 focus:outline-none transition-all text-sm ${
                speech.isProcessing
                  ? 'border-blue-500/50 ring-1 ring-blue-500/20 placeholder-blue-400/60'
                  : speech.isListening
                  ? 'border-red-500/50 ring-1 ring-red-500/20 placeholder-red-400/60'
                  : 'border-slate-700/60 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20'
              }`}
            />
            {speech.isListening && (
              <span className="absolute right-4 top-1/2 -translate-y-1/2 flex gap-0.5 items-end h-4">
                {[0, 1, 2, 3].map(i => (
                  <span
                    key={i}
                    className="w-0.5 bg-red-400 rounded-full animate-[soundbar_0.8s_ease-in-out_infinite]"
                    style={{ animationDelay: `${i * 0.15}s`, height: '60%' }}
                  />
                ))}
              </span>
            )}
            {speech.isProcessing && (
              <span className="absolute right-4 top-1/2 -translate-y-1/2">
                <Loader2 size={14} className="text-blue-400 animate-spin" />
              </span>
            )}
          </div>
          <VoiceMicButton
            speech={speech}
            onTranscript={(text) => { setQuery(text); setIsTyping(true); }}
            iconSize={16}
            className={`w-[46px] h-full rounded-2xl flex items-center justify-center transition-all ${
              speech.isListening
                ? 'bg-red-500/20 border border-red-500/50 text-red-400'
                : 'bg-slate-900/80 border border-slate-700/60 text-slate-400 hover:text-slate-200 hover:border-slate-600'
            }`}
          />
          <button
            onClick={() => handleSubmit(query || suggestions[currentSuggestion])}
            className="btn-primary shrink-0 flex items-center gap-2"
          >
            <Send size={15} />
            <span className="hidden sm:inline">Zapytaj</span>
          </button>
        </div>

        {/* Quick suggestion chips */}
        <div className="flex flex-wrap gap-2 mt-4">
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
  );
};

export default PromptBar;
