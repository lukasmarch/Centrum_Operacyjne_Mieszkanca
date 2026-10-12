import React, { useEffect, useState } from 'react';
import { Article } from '../../types';
import type { OutageItem, OutageOutlook } from '../../src/hooks/useOutageOutlook';
import { Tag, TagTone, dayWord, hourSpan, hm } from './tv';

/**
 * Belka — stan prądu i wody w Twojej wsi, w języku paska informacyjnego.
 *
 * Plakietka (kto + kiedy) nad białym pasem (co) i żółty pasek kontekstu
 * (co jeszcze w gminie). Zastępuje dwie rzeczy naraz: czerwoną kartę
 * `AlertOfTheDay`, która istniała tylko w oknie 30 h, i brak jakiejkolwiek
 * odpowiedzi w spokojny dzień. Krytyka 11.10.2026: zapowiedziane wyłączenie
 * w Grądach stało czwarte na liście wiadomości, a strona nigdy nie mówiła
 * „u Ciebie nic nie zapowiedziano”.
 *
 * Kolor = znaczenie. Czerwień tylko dla sprawy TERAZ albo w ciągu doby i tylko
 * w Twojej wsi (albo w gminie, gdy wsi nie wybrano). Zapowiedź dalej niż doba
 * — żółć. Spokój — chaber. Brak odpowiedzi z serwera — szew, i zdanie, że nie
 * sprawdziliśmy: „bez awarii” wolno powiedzieć wyłącznie po udanym sprawdzeniu.
 */

/** Ile godzin naprzód sprawa jest „pilna” — ta sama skala co przypięcie feedu (30 h) z zapasem na całą jutrzejszą dobę. */
const URGENT_H = 36;

const isUrgent = (item: OutageItem, now: Date) =>
    item.ongoing || (item.start !== null && item.start.getTime() - now.getTime() <= URGENT_H * 3_600_000);

/** „dziś 9:00–13:00”, a dla zgłoszenia bez terminu „zgłoszono 10:12”. */
const when = (item: OutageItem, now: Date): string => {
    if (item.start) return `${dayWord(item.start, now)} ${hourSpan(item.start, item.end)}`;
    if (item.reportedAt) return `zgłoszono ${dayWord(item.reportedAt, now) === 'dziś' ? '' : dayWord(item.reportedAt, now) + ' '}${hm(item.reportedAt)}`;
    return 'trwa';
};

const placesOf = (item: OutageItem) => (item.places.length ? item.places.join(', ') : 'gmina Rybno');

interface BeltState {
    tone: TagTone;
    tag: string;
    bar: string;
    context: React.ReactNode | null;
    articleId?: number;
}

function beltState(outlook: OutageOutlook, village: string | null, now: Date): BeltState {
    const items = outlook.items;
    const where = village ?? 'Gmina Rybno';
    const mine = village ? items.filter(i => i.concernsVillage) : items;
    const lead = mine[0];

    const contextFor = (exclude?: OutageItem) => {
        const other = items.find(i => i !== exclude && !(village && i.concernsVillage));
        if (other) {
            return (
                <>
                    W gminie: <strong className="font-extrabold">{when(other, now)}</strong> — {other.label.toLowerCase()}, {placesOf(other)}
                </>
            );
        }
        return `${village ? 'W całej gminie' : 'W gminie'} nic więcej nie zapowiedziano na ${outlook.windowDays} dni`;
    };

    if (lead) {
        const urgent = isUrgent(lead, now);
        const span = when(lead, now);
        return {
            tone: urgent ? 'red' : 'yellow',
            tag: urgent ? `${where} · ${lead.ongoing ? 'trwa teraz' : dayWord(lead.start ?? now, now)}` : `${where} · zapowiedź`,
            bar: village
                ? `${lead.label}: ${span}`
                : `${lead.label} — ${placesOf(lead)}: ${span}`,
            context: village && lead.places.length > 1
                ? <>Dotyczy też: {lead.places.filter(p => p !== village).join(', ')}</>
                : contextFor(lead),
            articleId: lead.id,
        };
    }

    // Okno czasu W SAMYM zdaniu: „bez wyłączeń” bez zakresu brzmi jak
    // gwarancja, a my wiemy tylko tyle, ile zapowiedziano na najbliższe dni
    return {
        tone: 'blue',
        tag: `${where} · teraz`,
        bar: `Najbliższe ${outlook.windowDays} dni: bez zapowiedzianych wyłączeń prądu i wody`,
        context: contextFor(),
    };
}

interface StatusBeltProps {
    outlook: OutageOutlook | null | undefined;
    village: string | null;
    /** Obowiązujące ostrzeżenie meteo z feedu (przypięte, nie-awaria) */
    weatherWarning: Article | null;
    onOpenDetails: () => void;
}

/**
 * Ruch belki gra WYŁĄCZNIE przy zmianie stanu (kontrakt kierunku, FORM).
 * Ostatni pokazany stan pamięta sessionStorage: wejście na pulpit z tym samym
 * stanem co poprzednio nie animuje niczego — inaczej „sygnatura” grałaby przy
 * każdym przejściu ze szkieletu do treści i przestałaby cokolwiek znaczyć.
 */
const SEEN_KEY = 'rl_belt_seen';

const readSeen = (): string | null => {
    try {
        return sessionStorage.getItem(SEEN_KEY);
    } catch {
        return null;
    }
};

const StatusBelt: React.FC<StatusBeltProps> = ({ outlook, village, weatherWarning, onOpenDetails }) => {
    const now = new Date();

    const state: BeltState | null = outlook === undefined
        ? null
        : outlook === null
            ? {
                tone: 'seam',
                tag: 'Prąd i woda',
                bar: 'Nie udało się sprawdzić komunikatów o awariach',
                context: 'Odśwież stronę za chwilę. Do tego czasu nie wiemy, czy coś zapowiedziano.',
            }
            : beltState(outlook, village, now);
    const key = state ? `${state.tone}|${state.bar}` : null;

    // Ostatni stan, który czytelnik już widział (z poprzedniego wejścia albo
    // sprzed odświeżenia co 10 min). Animujemy tylko różnicę
    const [shown, setShown] = useState<string | null>(readSeen);
    const animate = key !== null && shown !== null && shown !== key;

    useEffect(() => {
        if (!key) return;
        try {
            sessionStorage.setItem(SEEN_KEY, key);
        } catch {
            /* bez pamięci: brak animacji to bezpieczny wynik */
        }
        // Po zagraniu animacji kolejny render (np. zmiana wsi z powrotem) liczy od tego stanu
        const timer = setTimeout(() => setShown(key), 400);
        return () => clearTimeout(timer);
    }, [key]);

    // Zanim przyjdzie odpowiedź — miejsce zarezerwowane, żeby plakietki pod
    // spodem nie skakały o 90 px, gdy belka się pojawi
    if (!state || !key) {
        return (
            <section aria-label="Prąd i woda" aria-busy className="min-h-[124px]">
                <span className="block h-[25px] w-40 bg-tv-panel2" />
                <span className="mt-0 block h-[52px] w-full bg-tv-panel" />
            </section>
        );
    }

    const checked = outlook?.checkedAt ? hm(outlook.checkedAt) : null;

    return (
        <section aria-label="Prąd i woda" aria-live="polite">
            <Tag tone={state.tone} as="h2" className={`${animate ? "tv-tag-in " : ""}!text-[14px] !py-1.5`} key={`t-${key}`}>
                {state.tag}
            </Tag>
            <div key={`b-${key}`} className={`${animate ? "tv-wipe " : ""}bg-tv-paper px-4 py-3 lg:px-6 lg:py-5`}>
                <p className="font-cond text-[24px] font-extrabold leading-[1.08] text-tv-ink sm:text-[30px] lg:text-[44px]">
                    {state.bar}
                </p>
            </div>
            {state.context && (
                <p className="bg-tv-yellow px-4 py-2 text-[15px] font-semibold leading-snug text-tv-ink lg:px-5">
                    {state.context}
                    {outlook && (
                        <span className="font-normal">
                            {' · '}wg komunikatów Energi i ZGK{checked && <>, sprawdzone <span className="tabular">{checked}</span></>}
                        </span>
                    )}
                    {state.articleId !== undefined && (
                        <>
                            {' · '}
                            <button
                                onClick={onOpenDetails}
                                className="font-extrabold underline underline-offset-2 hover:no-underline"
                            >
                                szczegóły komunikatu
                            </button>
                        </>
                    )}
                </p>
            )}

            {weatherWarning && (
                <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-l-0 bg-tv-panel px-4 py-2.5">
                    <Tag tone="yellow">Ostrzeżenie</Tag>
                    <p className="min-w-0 flex-1 text-[15px] font-semibold leading-snug text-white">
                        {weatherWarning.title}
                    </p>
                </div>
            )}
        </section>
    );
};

export default StatusBelt;
