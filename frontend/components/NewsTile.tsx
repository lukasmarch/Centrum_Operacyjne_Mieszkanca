import React from 'react';
import { Newspaper, TrendingUp, ExternalLink, AlertTriangle } from 'lucide-react';
import { useArticles } from '../src/hooks/useArticles';
import ArticleImage from './ArticleImage';
import { AppSection } from '../types';

const getCategoryBadge = (category: string) => {
  const cat = (category || '').toLowerCase();
  const label = category?.toUpperCase() || 'INFO';
  if (cat.includes('awari'))
    return { label: 'AWARIA', color: 'text-red-400 bg-red-500/15 border-red-500/30', dot: 'bg-red-400' };
  return { label, color: 'text-slate-400 bg-slate-500/10 border-slate-600/30', dot: 'bg-slate-500' };
};

const getTimeAgo = (timestamp: string) => {
  if (!timestamp) return '';
  const d = new Date(timestamp);
  if (isNaN(d.getTime())) return timestamp;
  const diffMs = Date.now() - d.getTime();
  const diffH = Math.floor(diffMs / 3600000);
  if (diffH < 1) return 'przed chwilą';
  if (diffH < 24) return `${diffH}h temu`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD}d temu`;
};

interface NewsTileProps {
  onNavigate?: (section: AppSection) => void;
}

const NewsTile: React.FC<NewsTileProps> = ({ onNavigate }) => {
  const { articles, loading } = useArticles({ limit: 20 });

  // Category stats from all articles
  const categoryStats = React.useMemo(() => {
    if (!articles) return [];
    const counts: Record<string, number> = {};
    articles.forEach(a => {
      const cat = a.category || 'Inne';
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([cat, count]) => ({ category: cat, count, badge: getCategoryBadge(cat) }));
  }, [articles]);

  // Awaria articles always featured first (backend already sorts them first)
  const awaria = articles?.filter(a => (a.category || '').toLowerCase().includes('awari')) ?? [];
  const featured = articles?.[0];
  const restArticles = articles?.slice(1, 4);

  return (
    <div className="h-full flex flex-col p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Newspaper size={14} className="text-blue-400" />
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Najnowsze Wiadomości</span>
        </div>
        {articles && (
          <span className="text-[9px] font-bold text-slate-500">{articles.length} artykułów</span>
        )}
      </div>

      {/* Awaria alert banner */}
      {awaria.length > 0 && !loading && (
        <button
          onClick={() => onNavigate?.('news')}
          className="flex items-center gap-2 px-3 py-2 mb-3 rounded-xl bg-red-500/15 border border-red-500/30 hover:bg-red-500/25 transition-colors text-left w-full"
        >
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
          </span>
          <AlertTriangle size={11} className="text-red-400 shrink-0" />
          <span className="text-[10px] font-bold text-red-300 flex-1 truncate">
            {awaria.length === 1
              ? `AWARIA: ${awaria[0].title}`
              : `${awaria.length} awarie/ostrzeżenia – kliknij aby zobaczyć`}
          </span>
        </button>
      )}

      {loading ? (
        <div className="flex-1 grid grid-cols-3 gap-4 animate-pulse">
          <div className="col-span-2 space-y-3">
            <div className="h-40 bg-slate-800/50 rounded-xl" />
            <div className="h-14 bg-slate-800/50 rounded-xl" />
          </div>
          <div className="space-y-2">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-8 bg-slate-800/50 rounded-lg" />
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex gap-4">
          {/* Left: Featured + list */}
          <div className="flex-1 flex flex-col min-w-0 gap-3">
            {/* Featured article - big image */}
            {featured && (
              <a
                href={featured.url}
                target="_blank"
                rel="noopener noreferrer"
                className="relative rounded-xl overflow-hidden group cursor-pointer block"
                style={{ minHeight: '140px' }}
              >
                <div className="w-full min-h-[140px] max-h-[160px] overflow-hidden group-hover:[&_img]:scale-105">
                  <ArticleImage
                    imageUrl={featured.imageUrl}
                    category={featured.category}
                    source={featured.source}
                    className="transition-transform duration-500"
                    iconSize="lg"
                  />
                </div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />

                {/* Badge + title overlay */}
                <div className="absolute bottom-0 left-0 right-0 p-4">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`text-[8px] font-bold uppercase px-1.5 py-0.5 rounded border ${getCategoryBadge(featured.category || featured.source).color}`}>
                      {getCategoryBadge(featured.category || featured.source).label}
                    </span>
                    <span className="text-[9px] text-slate-400">{getTimeAgo(featured.timestamp)}</span>
                  </div>
                  <h4 className="text-sm font-bold text-white leading-snug line-clamp-2 group-hover:text-blue-300 transition-colors">
                    {featured.title}
                  </h4>
                </div>
                <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <ExternalLink size={14} className="text-white/70" />
                </div>
              </a>
            )}

            {/* Secondary articles */}
            <div className="space-y-1">
              {restArticles?.map(article => {
                const badge = getCategoryBadge(article.category || article.source);
                return (
                  <a
                    key={article.id}
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex gap-3 p-2 rounded-xl hover:bg-white/5 transition-colors group items-center"
                  >
                    {/* Thumbnail */}
                    <div className="w-16 h-16 rounded-lg overflow-hidden shrink-0 border border-white/5">
                      <ArticleImage
                        imageUrl={article.imageUrl}
                        category={article.category}
                        source={article.source}
                        iconSize="sm"
                      />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-[8px] font-bold uppercase px-1.5 py-0.5 rounded border ${badge.color}`}>
                          {badge.label}
                        </span>
                        <span className="text-[9px] text-slate-500">{getTimeAgo(article.timestamp)}</span>
                      </div>
                      <p className="text-[11px] font-semibold text-slate-200 leading-snug line-clamp-2 group-hover:text-blue-300 transition-colors">
                        {article.title}
                      </p>
                    </div>
                  </a>
                );
              })}
            </div>
          </div>

          {/* Right: Category statistics panel */}
          <div className="w-48 shrink-0 flex flex-col">
            <div className="flex items-center gap-1.5 mb-3">
              <TrendingUp size={11} className="text-blue-400" />
              <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">Kategorie</span>
            </div>

            <div className="space-y-1.5 flex-1">
              {categoryStats.map(({ category, count, badge }) => (
                <div
                  key={category}
                  className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg bg-slate-800/40 border border-white/5 hover:bg-slate-800/60 transition-colors"
                >
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${badge.dot}`} />
                  <span className="text-[10px] font-medium text-slate-300 flex-1 truncate">{badge.label}</span>
                  <span className="text-[10px] font-black text-slate-400">{count}</span>
                </div>
              ))}
            </div>

            {/* Mini summary */}
            <div className="mt-auto pt-3 border-t border-white/5">
              <div className="flex items-center justify-between">
                <span className="text-[9px] text-slate-600">Źródeł: {categoryStats.length}</span>
                <button
                  onClick={() => onNavigate?.('news')}
                  className="text-[9px] text-blue-400 font-semibold cursor-pointer hover:text-blue-300 transition-colors"
                >
                  Wszystkie →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NewsTile;
