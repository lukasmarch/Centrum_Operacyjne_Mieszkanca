import React from 'react';
import { ArrowRight } from 'lucide-react';
import { useDailySummary } from '../src/hooks/useDailySummary';
import { AppSection } from '../types';

interface AIBriefingTileProps {
  onNavigate?: (section: AppSection) => void;
}

const AIBriefingTile: React.FC<AIBriefingTileProps> = ({ onNavigate }) => {
  const { summary, loading, lastUpdated } = useDailySummary();

  const formatTimeAgo = (date: Date | null) => {
    if (!date) return '';
    const mins = Math.floor((Date.now() - date.getTime()) / 60000);
    if (mins < 1) return 'przed chwilą';
    if (mins < 60) return `${mins} min temu`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h temu`;
    return 'wczoraj';
  };

  return (
    <div className="h-full flex flex-col p-6 relative overflow-hidden">
      {/* Decorative gradient blobs */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-transparent to-purple-900/20 pointer-events-none" />
      <div className="absolute -top-10 -right-10 w-40 h-40 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 flex flex-col h-full">

        {/* Header badge */}
        <div className="flex items-center gap-2 mb-4">
          <span className="bg-blue-600 text-white px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider shadow-lg shadow-blue-500/20">
            AI Briefing
          </span>
          <div className={`w-2 h-2 rounded-full ${loading ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}`} />
          {lastUpdated && (
            <span className="text-[10px] text-slate-500 font-mono ml-auto">
              {formatTimeAgo(lastUpdated)}
            </span>
          )}
        </div>

        {/* Content */}
        {loading ? (
          <div className="space-y-3 animate-pulse flex-1">
            <div className="h-6 bg-slate-800/80 rounded-lg w-3/4" />
            <div className="h-4 bg-slate-800/80 rounded w-full" />
            <div className="h-4 bg-slate-800/80 rounded w-5/6" />
            <div className="h-4 bg-slate-800/80 rounded w-4/5" />
          </div>
        ) : summary ? (
          <>
            <h3 className="text-xl font-bold text-white leading-snug mb-3">
              {summary.headline}
            </h3>

            <div className="space-y-2 flex-1">
              {Array.isArray(summary.highlights) && summary.highlights.slice(0, 3).map((h, i) => (
                <div key={i} className="flex gap-2 items-start">
                  <span className="text-blue-400 mt-1 text-xs shrink-0">▸</span>
                  <p className="text-sm text-slate-300 leading-relaxed line-clamp-2">{h}</p>
                </div>
              ))}
            </div>

            {/* Stats bar */}
            {summary.stats && (
              <div className="flex items-center gap-4 mt-4 pt-4 border-t border-white/5">
                <div>
                  <p className="text-2xl font-black text-blue-400 leading-none">{summary.stats.total_articles}</p>
                  <p className="text-[10px] text-slate-500 uppercase mt-0.5">artykułów</p>
                </div>
                <div className="w-px h-8 bg-white/5" />
                <div>
                  <p className="text-2xl font-black text-purple-400 leading-none">{summary.stats.events_count}</p>
                  <p className="text-[10px] text-slate-500 uppercase mt-0.5">wydarzeń</p>
                </div>
                <div className="w-px h-8 bg-white/5" />
                <div>
                  <p className="text-2xl font-black text-emerald-400 leading-none">{summary.stats.categories_count}</p>
                  <p className="text-[10px] text-slate-500 uppercase mt-0.5">kategorii</p>
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-slate-500 italic flex-1">
            Briefing generowany codziennie o 7:00...
          </p>
        )}

        <button
          onClick={() => onNavigate?.('news')}
          className="mt-4 flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 font-semibold transition-colors group"
        >
          Czytaj pełny raport
          <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
        </button>
      </div>
    </div>
  );
};

export default AIBriefingTile;
