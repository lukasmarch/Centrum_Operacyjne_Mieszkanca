import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle, Clock, Sparkles } from 'lucide-react';
import { useArticles } from '../src/hooks/useArticles';
import ArticleImage, { getCategoryTheme } from './ArticleImage';
import { Article } from '../types';

interface NewsFeedProps {
  initialCategory?: string;
}

const getDateGroup = (rawTimestamp: string): 'today' | 'yesterday' | 'older' => {
  if (!rawTimestamp) return 'older';
  const d = new Date(rawTimestamp);
  if (isNaN(d.getTime())) return 'older';
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart.getTime() - 86400000);
  if (d >= todayStart) return 'today';
  if (d >= yesterdayStart) return 'yesterday';
  return 'older';
};

const DATE_GROUP_LABELS: Record<string, { label: string; icon: React.ReactNode }> = {
  today: { label: 'Dzisiaj', icon: <Sparkles size={12} className="text-blue-400" /> },
  yesterday: { label: 'Wczoraj', icon: <Clock size={12} className="text-neutral-500" /> },
  older: { label: 'Starsze', icon: <Clock size={12} className="text-neutral-600" /> },
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

const ArticleCard: React.FC<{ article: Article }> = ({ article }) => {
  const theme = getCategoryTheme(article.category);
  const isAwaria = (article.category || '').toLowerCase().includes('awari');

  return (
    <div className={`group glass-panel rounded-2xl overflow-hidden border shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col h-full hover:bg-white/5 ${isAwaria ? 'border-red-500/30 hover:border-red-500/50' : 'border-white/10'
      }`}>
      {/* Image */}
      <div className="h-44 overflow-hidden relative">
        <ArticleImage
          imageUrl={article.imageUrl}
          category={article.category}
          source={article.source}
          className="group-hover:scale-105 transition-transform duration-500"
          iconSize="lg"
        />
        {/* Category badge overlay */}
        <div className="absolute top-3 left-3">
          <span className={`backdrop-blur-md px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider border bg-gray-950/70 ${theme.badge}`}>
            {article.category || 'INFO'}
          </span>
        </div>
        {/* Time badge */}
        <div className="absolute top-3 right-3">
          <span className="backdrop-blur-md bg-gray-950/70 text-neutral-300 px-2 py-1 rounded-lg text-[9px] font-medium border border-white/10">
            {getTimeAgo(article.rawTimestamp || article.timestamp)}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wide">{article.source}</span>
        </div>
        <h3 className="text-base font-bold text-neutral-200 mb-2 group-hover:text-blue-400 transition-colors leading-snug line-clamp-2">
          {article.title}
        </h3>
        {article.summary && article.summary !== 'Brak opisu' && (
          <p className="text-sm text-neutral-400 line-clamp-3 mb-4 flex-1">
            {article.summary}
          </p>
        )}
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full py-2.5 rounded-xl bg-white/5 text-neutral-300 font-bold text-sm hover:bg-blue-600 hover:text-white transition-all text-center border border-white/5 mt-auto"
        >
          Czytaj więcej
        </a>
      </div>
    </div>
  );
};

const VISIBLE_CHIPS = 4;

const NewsFeed: React.FC<NewsFeedProps> = ({ initialCategory }) => {
  const { articles, loading, error } = useArticles({ limit: 50, perSource: 5, days: 2 });
  const [activeCategory, setActiveCategory] = useState<string>(initialCategory || 'Wszystkie');
  const [chipsExpanded, setChipsExpanded] = useState(false);

  // Category counts
  const categoryCounts = useMemo(() => {
    if (!articles) return {} as Record<string, number>;
    const counts: Record<string, number> = {};
    articles.forEach(a => {
      const cat = a.category || 'Inne';
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  }, [articles]);

  // Sorted categories: Awaria first, then by count desc
  const sortedCategories = useMemo(() => {
    if (!articles) return [];
    return Object.entries(categoryCounts)
      .sort((a, b) => {
        const aIsAwaria = a[0].toLowerCase().includes('awari');
        const bIsAwaria = b[0].toLowerCase().includes('awari');
        if (aIsAwaria && !bIsAwaria) return -1;
        if (!aIsAwaria && bIsAwaria) return 1;
        return b[1] - a[1];
      })
      .map(([cat]) => cat);
  }, [categoryCounts, articles]);

  const visibleCategories = chipsExpanded
    ? sortedCategories
    : sortedCategories.slice(0, VISIBLE_CHIPS);

  const overflowCount = sortedCategories.length - VISIBLE_CHIPS;

  // Filtered articles
  const filteredArticles = useMemo(() => {
    if (!articles) return [];

    if (activeCategory === 'Wszystkie') {
      const uniqueCategories = Array.from(new Set(articles.map(a => a.category).filter(Boolean)));
      return uniqueCategories.flatMap(cat =>
        articles.filter(a => a.category === cat).slice(0, 5)
      );
    }

    return articles
      .filter(a => a.category === activeCategory)
      .slice(0, 10);
  }, [articles, activeCategory]);

  // Group by date
  const groupedArticles = useMemo(() => {
    const groups: Record<string, Article[]> = { today: [], yesterday: [], older: [] };
    filteredArticles.forEach(a => {
      const group = getDateGroup(a.rawTimestamp);
      groups[group].push(a);
    });
    return groups;
  }, [filteredArticles]);

  if (loading) return (
    <div className="space-y-6">
      <div className="h-8 w-40 bg-gray-900/50 rounded-xl animate-pulse" />
      <div className="flex gap-2">
        {[1, 2, 3, 4].map(i => <div key={i} className="h-8 w-24 bg-gray-900/50 rounded-full animate-pulse" />)}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} className="h-72 bg-gray-900/30 rounded-2xl animate-pulse" />
        ))}
      </div>
    </div>
  );

  if (error) return <div className="text-center p-8 text-red-500">Błąd: {error}</div>;
  if (!articles || articles.length === 0) return <div className="text-center p-8 text-neutral-500">Brak wiadomości.</div>;

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex items-center gap-3">
        <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-violet-400">Aktualności</h2>
        <span className="text-xs font-bold text-neutral-600 bg-gray-900/50 px-2 py-0.5 rounded-full">{articles.length} artykułów</span>
      </div>

      {/* Categories – compact chips with overflow */}
      <div className="flex flex-wrap gap-2 items-center">
        {/* "Wszystkie" chip */}
        <button
          onClick={() => setActiveCategory('Wszystkie')}
          className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 border ${activeCategory === 'Wszystkie'
              ? 'bg-blue-600/20 text-blue-300 border-blue-500/30 shadow-lg shadow-blue-500/10'
              : 'bg-white/5 text-neutral-400 border-white/5 hover:bg-white/10'
            }`}
        >
          Wszystkie
          <span className="text-[10px] font-black bg-white/10 px-1.5 rounded">{articles.length}</span>
        </button>

        {/* Visible category chips */}
        {visibleCategories.map(cat => {
          const isAwaria = cat.toLowerCase().includes('awari');
          const count = categoryCounts[cat] || 0;
          const theme = getCategoryTheme(cat);
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 border ${activeCategory === cat
                  ? `${theme.badge} shadow-lg`
                  : 'bg-white/5 text-neutral-400 border-white/5 hover:bg-white/10'
                }`}
            >
              {isAwaria && <AlertTriangle size={10} />}
              <div className={`w-1.5 h-1.5 rounded-full ${theme.dot}`} />
              {cat}
              <span className="text-[10px] font-black bg-white/10 px-1.5 rounded">{count}</span>
            </button>
          );
        })}

        {/* Overflow toggle */}
        {overflowCount > 0 && (
          <button
            onClick={() => setChipsExpanded(prev => !prev)}
            className="px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-neutral-400 border border-white/5 hover:bg-white/10 transition-all flex items-center gap-1"
          >
            {chipsExpanded ? (
              <>Ukryj <ChevronUp size={10} /></>
            ) : (
              <>+{overflowCount} więcej <ChevronDown size={10} /></>
            )}
          </button>
        )}
      </div>

      {/* Articles grouped by date */}
      {(['today', 'yesterday', 'older'] as const).map(group => {
        const groupArticles = groupedArticles[group];
        if (groupArticles.length === 0) return null;
        const groupInfo = DATE_GROUP_LABELS[group];
        return (
          <div key={group} className="space-y-4">
            <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-2">
              <span className="h-px flex-1 bg-white/5" />
              {groupInfo.icon}
              {groupInfo.label}
              <span className="text-neutral-600 font-medium">({groupArticles.length})</span>
              <span className="h-px flex-1 bg-white/5" />
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {groupArticles.map(article => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          </div>
        );
      })}

      {filteredArticles.length === 0 && (
        <div className="text-center py-16 text-neutral-500">
          <div className="text-4xl mb-3">📰</div>
          Brak artykułów w kategorii „{activeCategory}".
        </div>
      )}
    </div>
  );
};

export default NewsFeed;
