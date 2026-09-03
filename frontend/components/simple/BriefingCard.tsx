import React from 'react';
import { Sparkles, ArrowRight } from 'lucide-react';
import { useDailySummary } from '../../src/hooks/useDailySummary';

/**
 * Briefing dnia w trybie prostym — nagłówek AI i pierwsze zdania omówienia.
 *
 * Pełna wersja (kategorie, źródła, statystyki) żyje na stronie wiadomości;
 * tutaj chodzi o jedno: żeby wchodzący w pięć sekund wiedział, co się dzieje.
 * Bez briefingu strona główna miała same widżety i ani jednego zdania treści.
 */

const renderBold = (text: string): React.ReactNode =>
    text.split(/(\*\*.*?\*\*)/g).map((part, i) =>
        part.startsWith('**') && part.endsWith('**')
            ? <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>
            : <span key={i}>{part}</span>,
    );

// Polskie skróty kończące się kropką, która NIE kończy zdania.
// 3.09.2026 strona główna pokazała „Utrudnienia dotyczą m.in." i na tym się
// urywała: dzielenie po samym `[.!?]` uznało kropkę w „m.in." za koniec
// trzeciego zdania. Lista jest krótsza niż wyjątki, które by ją zastąpiły.
const ABBREVIATIONS = new Set([
    'm.in.', 'np.', 'itp.', 'itd.', 'tj.', 'ok.', 'ul.', 'godz.', 'proc.',
    'r.', 'ww.', 'br.', 'woj.', 'gm.', 'nr.', 'tzw.', 'ds.', 'ub.',
]);

/** Pierwsze zdania omówienia — tyle, ile mieści się bez zwijania na telefonie. */
const firstSentences = (text: string, count = 3): string => {
    const sentences: string[] = [];
    let current: string[] = [];

    for (const word of text.split(/\s+/)) {
        current.push(word);
        const ends = /[.!?]$/.test(word) && !ABBREVIATIONS.has(word.toLowerCase());
        if (ends) {
            sentences.push(current.join(' '));
            current = [];
            if (sentences.length >= count) break;
        }
    }
    if (!sentences.length) return text;
    return sentences.join(' ').trim();
};


interface BriefingCardProps {
    onShowAll: () => void;
}

const BriefingCard: React.FC<BriefingCardProps> = ({ onShowAll }) => {
    const { summary, loading, lastUpdated } = useDailySummary();

    // Bez briefingu nie pokazujemy pustej ramki — ta sama zasada co przy alercie
    if (loading || !summary?.headline) return null;

    // Godzina zegarowa, nie „5h temu": briefing powstaje o 7:00 i jest odświeżany
    // o 13:30, więc dopiero konkretna godzina mówi, którą wersję masz przed sobą
    const updated = lastUpdated?.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });

    return (
        <section aria-label="Briefing dnia" className="rounded-2xl border border-white/10 bg-[#0d1117] p-5 lg:p-6">
            <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-blue-400" aria-hidden />
                <span className="text-xs font-bold uppercase tracking-widest text-blue-400">Briefing dnia</span>
                {updated && <span className="text-xs text-neutral-500">· {updated}</span>}
            </div>

            <h2 className="mt-3 text-xl lg:text-2xl font-bold leading-snug text-white">
                {summary.headline}
            </h2>

            {summary.highlights && (
                <p className="mt-2 text-base leading-relaxed text-neutral-300">
                    {renderBold(firstSentences(summary.highlights))}
                </p>
            )}

            <button
                onClick={onShowAll}
                className="mt-3 flex min-h-[44px] items-center gap-1.5 text-sm font-semibold text-blue-400 transition-colors hover:text-blue-300"
            >
                Czytaj wszystkie wiadomości
                <ArrowRight size={15} aria-hidden />
            </button>
        </section>
    );
};

export default BriefingCard;
