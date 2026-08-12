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
            className="flex min-h-[56px] items-center gap-3 rounded-full border border-blue-500/30 bg-[#0d1117] px-5 py-2 transition-colors focus-within:border-blue-500/60"
        >
            <MessageCircle size={20} className="shrink-0 text-blue-400" aria-hidden />
            <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Zapytaj o cokolwiek w gminie…"
                aria-label="Zapytaj asystenta o cokolwiek w gminie"
                className="min-w-0 flex-1 bg-transparent text-base text-white placeholder:text-neutral-500 outline-none"
            />
            <button
                type="submit"
                aria-label="Zapytaj"
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-500 text-white transition-colors hover:bg-blue-400 lg:w-auto lg:px-5"
            >
                <ArrowUp size={18} className="lg:hidden" aria-hidden />
                <span className="hidden lg:inline text-sm font-semibold">Zapytaj</span>
            </button>
        </form>
    );
};

export default AskBar;
