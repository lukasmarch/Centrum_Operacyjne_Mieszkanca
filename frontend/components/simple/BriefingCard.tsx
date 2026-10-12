import React from 'react';
import { useDailySummary } from '../../src/hooks/useDailySummary';
import { RowLink, Tag } from './tv';

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

/**
 * Dzień briefingu słowami. API oddaje NAJNOWSZY wiersz, więc przed pierwszym
 * przebiegiem dnia (albo gdy przebieg padł) na stronie stoi wczorajszy — a bez
 * daty czytał się jak dzisiejszy (audyt F-016). Wczorajszy i starszy dostają
 * wyróżnienie: to nie jest drobiazg, tylko informacja, że treść może być nieaktualna.
 */
export const briefingDay = (generated: Date, now: Date): { label: string; stale: boolean } => {
    const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const days = Math.round((startOf(now) - startOf(generated)) / 86_400_000);
    if (days <= 0) return { label: 'dziś', stale: false };
    if (days === 1) return { label: 'wczoraj', stale: true };
    return {
        label: generated.toLocaleDateString('pl-PL', { day: 'numeric', month: 'long' }),
        stale: true,
    };
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
    const day = lastUpdated ? briefingDay(lastUpdated, new Date()) : null;

    // Briefing z wczoraj (przebieg jeszcze nie ruszył albo padł) NIE może stać
    // na stronie jak dzisiejszy. Do 11.10.2026 zmieniał tylko kolor etykiety,
    // a nagłówek dalej mówił „Dziś w Rybnie odbywa się…” o wczorajszym dniu —
    // pierwsza treść na stronie zaprzeczała własnemu znacznikowi czasu.
    // Teraz zwija się do jednej linii z datą: tekst, który mówi „dziś”, pokazuje
    // się wyłącznie w dniu, którego dotyczy.
    if (day?.stale) {
        return (
            <section aria-label="Briefing dnia" className="flex flex-wrap items-center justify-between gap-x-4 border-y border-tv-seam py-2">
                <p className="text-[15px] text-tv-muted">
                    Dzisiejszy briefing jeszcze nie powstał. Ostatni: <span className="font-semibold text-tv-paper">{day.label}, {updated}</span>
                </p>
                <RowLink onClick={onShowAll}>Wiadomości z gminy</RowLink>
            </section>
        );
    }

    return (
        <section aria-label="Briefing dnia">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <Tag as="h2">Briefing dnia</Tag>
                {updated && <span className="tabular text-[15px] text-tv-muted">dziś, {updated}</span>}
            </div>
            <div className="border-t-2 border-tv-blue bg-tv-panel px-4 pb-2 pt-3 lg:px-5">
                <p className="font-cond text-[22px] font-extrabold leading-snug text-white lg:text-[26px]">
                    {summary.headline}
                </p>
                {summary.highlights && (
                    <p className="mt-2 max-w-[70ch] text-[16px] leading-relaxed text-[#d7dbe8]">
                        {renderBold(firstSentences(summary.highlights))}
                    </p>
                )}
                <RowLink onClick={onShowAll}>Czytaj wszystkie wiadomości</RowLink>
            </div>
        </section>
    );
};

export default BriefingCard;
