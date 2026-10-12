import React, { useState } from 'react';
import { MessageCircle, ArrowUp } from 'lucide-react';

interface AskBarProps {
    onAsk: (query: string) => void;
}

/**
 * Pigułka asystenta — uproszczone wejście do czatu (logika nawigacji jak
 * w PromptBar: zapytanie wędruje do AssistantPage przez initialQuery).
 * Mobile: sam placeholder; desktop: widoczny przycisk „Zapytaj".
 */
const AskBar: React.FC<AskBarProps> = ({ onAsk }) => {
    const [query, setQuery] = useState('');

    const submit = (e: React.FormEvent) => {
        e.preventDefault();
        const trimmed = query.trim();
        if (!trimmed) return;
        onAsk(trimmed);
        setQuery('');
    };

    return (
        <form
            onSubmit={submit}
            className="flex min-h-[60px] items-center gap-3 border-2 border-tv-seam bg-tv-panel pl-4 transition-colors focus-within:border-tv-paper"
        >
            <MessageCircle size={20} className="shrink-0 text-tv-muted" aria-hidden />
            <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Zapytaj asystenta o gminę…"
                aria-label="Zapytaj asystenta o cokolwiek w gminie"
                className="min-w-0 flex-1 bg-transparent py-3 text-[17px] text-white placeholder:text-tv-muted outline-none focus-visible:outline-none"
            />
            <button
                type="submit"
                aria-label="Zapytaj"
                className="font-cond flex min-h-[56px] w-14 shrink-0 items-center justify-center self-stretch bg-tv-blue text-white transition-colors hover:bg-[#3a63ff] lg:w-auto lg:px-6"
            >
                <ArrowUp size={18} className="lg:hidden" aria-hidden />
                <span className="hidden lg:inline text-[17px] font-extrabold uppercase tracking-wide">Zapytaj</span>
            </button>
        </form>
    );
};

export default AskBar;
