import React from 'react';
import { Newspaper, ExternalLink } from 'lucide-react';
import { useArticles } from '../src/hooks/useArticles';
import ArticleImage, { getCategoryTheme } from './ArticleImage';
import { AppSection } from '../types';

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

  const categoryStats = React.useMemo(() => {
    if (!articles) return [];
    const counts: Record<string, number> = {};
    articles.forEach(a => {
      const cat = a.category || 'Inne';
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([cat, count]) => ({ category: cat, count, theme: getCategoryTheme(cat) }));
  }, [articles]);

  const featured = articles?.[0];
  const restArticles = articles?.slice(1, 5);

  return (
    <div className="h-full flex flex-col p-4 sm:p-5">
      {/* ── Header: simple title + single link ── */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Newspaper size={16} className="text-blue-400" />
          <span className="text-xs sm:text-sm font-bold text-neutral-300 uppercase tracking-wider">
            Najnowsze Wiadomości
          </span>
        </div>
        <button
          onClick={() => onNavigate?.('news')}
          className="text-xs text-blue-400 font-semibold cursor-pointer hover:text-blue-300 transition-colors whitespace-nowrap"
        >
          Wszystkie →
        </button>
      </div>

      {/* ── Content ── */}
      {loading ? (
        <div className="flex-1 flex flex-col gap-2 animate-pulse">
          <div className="h-32 bg-gray-900/50 rounded-xl" />
          <div className="space-y-1">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-12 bg-gray-900/50 rounded-lg" />
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-h-0">
          {/* Featured article – hero card */}
          {featured && (() => {
            const theme = getCategoryTheme(featured.category);
            const isAwaria = (featured.category || '').toLowerCase().includes('awari');
            return (
              <a
                href={featured.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`relative rounded-xl overflow-hidden group cursor-pointer block flex-shrink-0 mb-2 ${isAwaria ? 'ring-1 ring-red-500/40' : ''}`}
              >
                <div className="w-full h-[120px] sm:h-[140px] overflow-hidden group-hover:[&_img]:scale-105">
                  <ArticleImage
                    imageUrl={featured.imageUrl}
                    category={featured.category}
                    source={featured.source}
                    className="transition-transform duration-500"
                    iconSize="lg"
                  />
                </div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />

                <div className="absolute bottom-0 left-0 right-0 p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded border ${theme.badge}`}>
                      {(featured.category || 'INFO').toUpperCase()}
                    </span>
                    <span className="text-[10px] text-neutral-400">{getTimeAgo(featured.timestamp)}</span>
                  </div>
                  <h4 className="text-sm sm:text-base font-bold text-white leading-snug line-clamp-2 group-hover:text-blue-300 transition-colors">
                    {featured.title}
                  </h4>
                </div>
                <div className="absolute top-2.5 right-2.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <ExternalLink size={12} className="text-white/70" />
                </div>
              </a>
            );
          })()}

          {/* Secondary articles – compact rows with dividers */}
          <div className="flex flex-col divide-y divide-white/5 flex-1">
            {restArticles?.map(article => {
              const theme = getCategoryTheme(article.category);
              const isAwaria = (article.category || '').toLowerCase().includes('awari');
              return (
                <a
                  key={article.id}
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`flex gap-3 py-2 px-1 hover:bg-white/5 transition-colors group items-center ${isAwaria ? 'bg-red-500/5' : ''}`}
                >
                  {/* Thumbnail */}
                  <div className="w-11 h-11 sm:w-12 sm:h-12 rounded-lg overflow-hidden shrink-0 border border-white/5">
                    <ArticleImage
                      imageUrl={article.imageUrl}
                      category={article.category}
                      source={article.source}
                      iconSize="sm"
                    />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className={`text-[8px] font-bold uppercase px-1 py-px rounded border whitespace-nowrap ${theme.badge}`}>
                        {(article.category || 'INFO').toUpperCase()}
                      </span>
                      <span className="text-[9px] text-neutral-400 whitespace-nowrap">
                        {getTimeAgo(article.timestamp)}
                      </span>
                    </div>
                    <p className="text-xs sm:text-sm font-semibold text-neutral-200 leading-snug line-clamp-2 group-hover:text-blue-300 transition-colors">
                      {article.title}
                    </p>
                  </div>
                </a>
              );
            })}
          </div>

          {/* ── Footer: stats bar ── */}
          <div className="flex items-center gap-3 pt-2.5 mt-1 border-t border-white/5 flex-wrap">
            {/* Article count */}
            {articles && (
              <span className="text-[10px] sm:text-xs font-semibold text-neutral-400">
                {articles.length} artykułów
              </span>
            )}
            <span className="text-neutral-600">·</span>
            <span className="text-[10px] sm:text-xs text-neutral-400">
              Źródeł: {categoryStats.length}
            </span>

            {/* Category dots */}
            <span className="text-neutral-600 hidden sm:inline">·</span>
            <div className="hidden sm:flex items-center gap-2.5">
              {categoryStats.slice(0, 5).map(({ category, count, theme }) => (
                <span
                  key={category}
                  className="inline-flex items-center gap-1 text-[10px] text-neutral-400"
                  title={`${category}: ${count}`}
                >
                  <span className={`w-2 h-2 rounded-full ${theme.dot}`} />
                  <span className="font-medium uppercase">{category}</span>
                  <span className="font-black text-neutral-500">{count}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NewsTile;
