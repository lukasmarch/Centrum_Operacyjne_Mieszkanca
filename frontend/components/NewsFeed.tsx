import React, { useState, useMemo } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import { useArticles } from '../src/hooks/useArticles';
import ArticleImage from './ArticleImage';
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

const DATE_GROUP_LABELS: Record<string, string> = {
  today: 'Dzisiaj',
  yesterday: 'Wczoraj',
  older: 'Starsze',
};

const getCategoryBadge = (category: string) => {
  const cat = (category || '').toLowerCase();
  if (cat.includes('awari'))
    return { color: 'text-red-400 border-red-500/30 bg-red-500/10' };
  return { color: 'text-slate-400 border-slate-600/30 bg-slate-500/10' };
};

const ArticleCard: React.FC<{ article: Article }> = ({ article }) => {
  const badge = getCategoryBadge(article.category || '');
  return (
  <div className="group glass-panel rounded-3xl p-4 border border-white/10 shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col h-full hover:bg-white/5">
    {/* Image */}
    <div className="h-48 rounded-2xl overflow-hidden mb-4 relative">
      <ArticleImage
        imageUrl={article.imageUrl}
        category={article.category}
        source={article.source}
        className="group-hover:scale-105 transition-transform duration-500"
        iconSize="lg"
      />
      <div className="absolute top-3 left-3">
        <span className={`bg-slate-900/80 backdrop-blur-sm px-2 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider border ${badge.color}`}>
          {article.category}
        </span>
      </div>
    </div>

    {/* Content */}
    <div className="flex-1 flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-bold text-slate-500 uppercase">{article.source}</span>
        <span className="text-xs text-slate-600">•</span>
        <span className="text-xs text-slate-500">{article.timestamp}</span>
      </div>
      <h3 className="text-lg font-bold text-slate-200 mb-2 group-hover:text-blue-400 transition-colors leading-snug">
        {article.title}
      </h3>
      <p className="text-sm text-slate-400 line-clamp-3 mb-4 flex-1">
        {article.summary}
      </p>
      <a
        href={article.url}
        target="_blank"
        rel="noopener noreferrer"
        className="w-full py-2 rounded-xl bg-white/5 text-slate-300 font-bold text-sm hover:bg-blue-600 hover:text-white transition-all text-center border border-white/5"
      >
        Czytaj więcej
      </a>
    </div>
  </div>
  );
};

const AwariaCard: React.FC<{ article: Article }> = ({ article }) => (
  <a
    href={article.url}
    target="_blank"
    rel="noopener noreferrer"
    className="group flex gap-4 p-4 rounded-2xl bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 transition-all"
  >
    <div className="w-20 h-20 rounded-xl overflow-hidden shrink-0">
      <ArticleImage imageUrl={article.imageUrl} category={article.category} source={article.source} iconSize="md" />
    </div>
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] font-bold text-red-400 uppercase px-1.5 py-0.5 rounded border border-red-500/30 bg-red-500/15">
          AWARIA
        </span>
        <span className="text-[10px] text-slate-500">{article.source}</span>
        <span className="text-[10px] text-slate-600">•</span>
        <span className="text-[10px] text-slate-500">{article.timestamp}</span>
      </div>
      <h4 className="font-bold text-red-200 leading-snug group-hover:text-red-100 transition-colors line-clamp-2">
        {article.title}
      </h4>
      {article.summary && article.summary !== 'Brak opisu' && (
        <p className="text-sm text-slate-400 mt-1 line-clamp-2">{article.summary}</p>
      )}
    </div>
  </a>
);

const VISIBLE_CHIPS = 3; // Non-Awaria chips visible before overflow

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

  const awaria = useMemo(() =>
    articles?.filter(a => (a.category || '').toLowerCase().includes('awari')) ?? [],
    [articles]
  );

  // Filtered articles (excluding Awaria when viewing all, they appear in separate section)
  const filteredArticles = useMemo(() => {
    if (!articles) return [];

    if (activeCategory === 'Wszystkie') {
      // Non-awaria articles, top 5 per category, sorted by date
      const nonAwaria = articles.filter(a => !(a.category || '').toLowerCase().includes('awari'));
      const uniqueCategories = Array.from(new Set(nonAwaria.map(a => a.category).filter(Boolean)));
      return uniqueCategories.flatMap(cat =>
        nonAwaria.filter(a => a.category === cat).slice(0, 5)
      );
    }

    if (activeCategory === 'Awaria') {
      return awaria;
    }

    return articles
      .filter(a => a.category === activeCategory)
      .slice(0, 10);
  }, [articles, activeCategory, awaria]);

  // Group by date
  const groupedArticles = useMemo(() => {
    const groups: Record<string, Article[]> = { today: [], yesterday: [], older: [] };
    filteredArticles.forEach(a => {
      const group = getDateGroup(a.rawTimestamp);
      groups[group].push(a);
    });
    return groups;
  }, [filteredArticles]);

  if (loading) return <div className="text-center p-8 text-slate-500 animate-pulse">Ładowanie wiadomości...</div>;
  if (error) return <div className="text-center p-8 text-red-500">Błąd: {error}</div>;
  if (!articles || articles.length === 0) return <div className="text-center p-8 text-slate-500">Brak wiadomości.</div>;

  const showAwariaSection = awaria.length > 0 && activeCategory === 'Wszystkie';

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-slate-100">Aktualności</h2>

      {/* Categories – compact chips with overflow */}
      <div className="flex flex-wrap gap-2 items-center">
        {/* "Wszystkie" chip */}
        <button
          onClick={() => setActiveCategory('Wszystkie')}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 border ${
            activeCategory === 'Wszystkie'
              ? 'bg-slate-700 text-white border-transparent'
              : 'bg-white/5 text-slate-400 border-white/5 hover:bg-white/10'
          }`}
        >
          Wszystkie
          <span className="text-[10px] font-black bg-white/10 px-1 rounded">{articles.length}</span>
        </button>

        {/* Visible category chips */}
        {visibleCategories.map(cat => {
          const isAwaria = cat.toLowerCase().includes('awari');
          const count = categoryCounts[cat] || 0;
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap flex items-center gap-1.5 border ${
                activeCategory === cat
                  ? isAwaria
                    ? 'bg-red-600/20 text-red-400 border-red-500/30'
                    : 'bg-slate-700 text-white border-transparent'
                  : 'bg-white/5 text-slate-400 border-white/5 hover:bg-white/10'
              }`}
            >
              {isAwaria && <AlertTriangle size={10} />}
              {cat}
              <span className="text-[10px] font-black bg-white/10 px-1 rounded">{count}</span>
            </button>
          );
        })}

        {/* Overflow toggle */}
        {overflowCount > 0 && (
          <button
            onClick={() => setChipsExpanded(prev => !prev)}
            className="px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-slate-400 border border-white/5 hover:bg-white/10 transition-all flex items-center gap-1"
          >
            {chipsExpanded ? (
              <>Ukryj <ChevronUp size={10} /></>
            ) : (
              <>+{overflowCount} więcej <ChevronDown size={10} /></>
            )}
          </button>
        )}
      </div>

      {/* WAŻNE section - Awaria articles always on top when viewing all */}
      {showAwariaSection && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
            </span>
            <h3 className="text-sm font-black text-red-400 uppercase tracking-wider">Ważne / Awarie</h3>
          </div>
          <div className="space-y-2">
            {awaria.map(article => (
              <AwariaCard key={article.id} article={article} />
            ))}
          </div>
          <div className="border-t border-white/5" />
        </div>
      )}

      {/* Articles grouped by date */}
      {(['today', 'yesterday', 'older'] as const).map(group => {
        const groupArticles = groupedArticles[group];
        if (groupArticles.length === 0) return null;
        return (
          <div key={group} className="space-y-4">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <span className="h-px flex-1 bg-white/5" />
              {DATE_GROUP_LABELS[group]}
              <span className="text-slate-600">({groupArticles.length})</span>
              <span className="h-px flex-1 bg-white/5" />
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {groupArticles.map(article => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          </div>
        );
      })}

      {filteredArticles.length === 0 && !showAwariaSection && (
        <div className="text-center py-12 text-slate-500">
          Brak artykułów w kategorii „{activeCategory}".
        </div>
      )}
    </div>
  );
};

export default NewsFeed;
