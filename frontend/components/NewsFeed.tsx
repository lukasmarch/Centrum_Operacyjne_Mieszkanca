import React, { useState, useMemo } from 'react';
import { useArticles } from '../src/hooks/useArticles';

const NewsFeed: React.FC = () => {
    const { articles, loading, error } = useArticles({ limit: 50, perSource: 5, days: 2 });
    const [activeCategory, setActiveCategory] = useState<string>('Wszystkie');

    // Group articles categories
    const categories = useMemo(() => {
        if (!articles) return [];
        const cats = new Set(articles.map(a => a.category).filter(Boolean));
        return ['Wszystkie', ...Array.from(cats)];
    }, [articles]);

    // Filter and Limit articles
    const filteredArticles = useMemo(() => {
        if (!articles) return [];

        let filtered = articles;

        if (activeCategory === 'Wszystkie') {
            // If "All", maybe we still want to limit total? 
            // Or maybe show top 3 from EACH category? Use flatMap approach if requested "top 3 latest entries per category"
            // The user said: "only the 3 latest entries from each category"
            // But usually "All" view aggregates them. Let's filter by active category first.

            // If "Wszystkie" is selected, let's show top 3 from each category? 
            // Or just top 9 overall? 
            // User: "in sections... most recent 3 entries from each category"

            // Let's implement groupings.
            // If activeCategory is 'Wszystkie', we iterate over all categories and pick top 3 from each, then result.
            // However, the UI design is a single grid.
            // If I just return top 3 overall it might be too few. 
            // Let's assume for 'Wszystkie' we simply show the latest ones (e.g. 12).
            // But if a specific category is selected, definitely top 3.

            // Re-reading user request: "remove unnecessary info, only 3 latest entries from each category"
            // This suggests a cleanup. 

            // Let's do this:
            // For 'Wszystkie', get all unique categories, get top 5 for each, combine and sort by date.
            const uniqueCategories = Array.from(new Set(articles.map(a => a.category).filter(Boolean)));

            // Since I don't have raw timestamp easily without changing useArticles, relying on index (assuming API returns sorted).
            // API returns sorted by scraped_at desc. So just taking slice(0, 5) per category works.

            return uniqueCategories.flatMap(cat =>
                articles.filter(a => a.category === cat).slice(0, 5)
            );
        }

        return articles
            .filter(a => a.category === activeCategory)
            .slice(0, 5);
    }, [articles, activeCategory]);

    if (loading) return <div className="text-center p-8 text-slate-500 animate-pulse">Ładowanie wiadomości...</div>;
    if (error) return <div className="text-center p-8 text-red-500">Błąd: {error}</div>;
    if (!articles || articles.length === 0) return <div className="text-center p-8 text-slate-500">Brak wiadomości.</div>;

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-100">Aktualności</h2>

            {/* Categories */}
            <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                {categories.map(cat => (
                    <button
                        key={cat}
                        onClick={() => setActiveCategory(cat)}
                        className={`px-4 py-2 rounded-full text-sm font-bold transition-all whitespace-nowrap ${activeCategory === cat
                            ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                            : 'bg-white/5 text-slate-400 hover:bg-white/10 border border-white/5'
                            }`}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Articles Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredArticles.map(article => (
                    <div key={article.id} className="group glass-panel rounded-3xl p-4 border border-white/10 shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col h-full hover:bg-white/5">
                        {/* Image */}
                        <div className="h-48 rounded-2xl bg-slate-800 overflow-hidden mb-4 relative">
                            {article.imageUrl ? (
                                <img
                                    src={article.imageUrl}
                                    alt={article.title}
                                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                                    onError={(e) => {
                                        (e.target as HTMLImageElement).style.display = 'none';
                                        (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                                    }}
                                />
                            ) : null}
                            <div className={`w-full h-full flex items-center justify-center text-4xl bg-slate-800 text-slate-600 ${article.imageUrl ? 'hidden' : ''}`}>
                                📰
                            </div>
                            <div className="absolute top-3 left-3">
                                <span className="bg-slate-900/80 backdrop-blur-sm px-2 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider text-blue-400 border border-blue-500/30">
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
                ))}
            </div>
        </div>
    );
};

export default NewsFeed;
