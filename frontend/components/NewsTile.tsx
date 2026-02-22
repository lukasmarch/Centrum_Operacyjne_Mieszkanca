import React from 'react';
import { Newspaper } from 'lucide-react';
import { useArticles } from '../src/hooks/useArticles';

const NewsTile: React.FC = () => {
  const { articles, loading } = useArticles({ limit: 6 });

  return (
    <div className="h-full flex flex-col p-5">

      <div className="flex items-center gap-2 mb-4">
        <Newspaper size={13} className="text-blue-400" />
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Wiadomości</p>
      </div>

      {/* Horizontal scroll strip */}
      <div className="flex-1 overflow-x-auto scrollbar-hide -mx-1 px-1">
        <div className="flex gap-3 pb-1 h-full" style={{ minWidth: 'max-content' }}>
          {loading
            ? Array(4).fill(0).map((_, i) => (
                <div key={i} className="w-44 h-32 bg-slate-800/60 rounded-2xl animate-pulse shrink-0" />
              ))
            : articles?.slice(0, 6).map(article => (
                <a
                  key={article.id}
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-44 shrink-0 bg-slate-800/60 border border-slate-700/50 rounded-2xl p-3.5 hover:border-blue-500/40 hover:bg-slate-800 transition-all group flex flex-col"
                >
                  <span className="text-[9px] font-bold uppercase text-blue-400 bg-blue-500/10 border border-blue-500/20 px-1.5 py-0.5 rounded self-start">
                    {article.source}
                  </span>
                  <p className="text-xs font-semibold text-slate-200 mt-2 leading-snug line-clamp-3 group-hover:text-blue-300 transition-colors flex-1">
                    {article.title}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-2 font-mono">{article.timestamp}</p>
                </a>
              ))}
        </div>
      </div>
    </div>
  );
};

export default NewsTile;
