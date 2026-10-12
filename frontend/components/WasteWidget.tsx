import React, { useState, useMemo } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import { WasteEvent } from '../types';
import { wasteData } from '../src/data/wasteSchedule';
import { Notice, Tag, dayWord } from './simple/tv';

interface WasteWidgetProps {
    events: WasteEvent[];
    town: string;
}

/**
 * Kolor pojemnika — JEDYNY kolor spoza palety `tv-*` na tej stronie, i to celowo:
 * to nie ozdoba, tylko informacja, którą mieszkaniec zna z podwórka (worek
 * żółty, niebieski, zielony, brązowy — jednolity system segregacji). Mały
 * kwadrat stoi obok NAZWY frakcji, nigdy zamiast niej. Frakcje bez ustalonego
 * koloru (zmieszane, popiół, gabaryty, elektrośmieci) kwadratu nie mają.
 * Do 11.10.2026 każda frakcja miała własną pastelową kartę (fiolet dla
 * „pozostałych”), więc kolor mieszał informację z dekoracją.
 */
const binColor = (type: string): string | null => {
    const lower = type.toLowerCase();
    if (lower.includes('bio')) return '#8a5a2b';
    if (lower.includes('metale')) return '#ffd23f';
    if (lower.includes('papier')) return '#2f6fe0';
    if (lower.includes('szkło')) return '#2e9e4f';
    return null;
};

const WasteType: React.FC<{ type: string; muted?: boolean }> = ({ type, muted = false }) => {
    const color = binColor(type);
    return (
        <span className={`flex items-center gap-2 ${muted ? 'text-tv-muted' : ''}`}>
            <span
                aria-hidden
                className="h-3 w-3 shrink-0"
                style={color ? { backgroundColor: color, opacity: muted ? 0.5 : 1 } : undefined}
            />
            {type}
        </span>
    );
};

const MONTHS_PL = ['Styczeń','Luty','Marzec','Kwiecień','Maj','Czerwiec','Lipiec','Sierpień','Wrzesień','Październik','Listopad','Grudzień'];

/** Data odbioru z `daysRemaining` — jak kafel „Wywóz” na pulpicie (bez zgadywania roku) */
const dateIn = (days: number) => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() + days);
    return d;
};

const inDays = (n: number) => (n === 0 ? 'dziś' : n === 1 ? 'jutro' : `za ${n} dni`);

const WasteWidget: React.FC<WasteWidgetProps> = ({ events, town }) => {
    const [fullOpen, setFullOpen] = useState(false);

    // Bez cichego „Rybno” → R1: nazwa musi być pozycją harmonogramu (F-039)
    const mappedTown = town;

    // Terminy zebrane po DNIU: papier, metale i szkło jeżdżą zwykle razem,
    // a mieszkaniec pyta „kiedy i co wystawić”, nie „kiedy papier”
    const upcomingDays = useMemo(() => {
        const byDay: { days: number; date: string; types: string[] }[] = [];
        // 10 odbiorów, nie 4 jak w dawnym kaflu bento: na własnej stronie lista
        // ma sięgać kilku tygodni, inaczej „kolejne terminy” to jeden wiersz
        events.slice(0, 10).forEach(ev => {
            const last = byDay[byDay.length - 1];
            if (last && last.days === ev.daysRemaining) last.types.push(ev.type);
            else byDay.push({ days: ev.daysRemaining, date: ev.originalDateString, types: [ev.type] });
        });
        return byDay;
    }, [events]);

    // Build full schedule grouped by month from raw wasteData
    const fullSchedule = useMemo(() => {
        const schedule = wasteData[mappedTown];
        if (!schedule) return [];

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        // month key -> list of { date, type, isPast }
        const byMonth: Record<string, { date: Date; dateStr: string; type: string; isPast: boolean }[]> = {};

        Object.entries(schedule).forEach(([wasteType, datesString]) => {
            if (!datesString || datesString === 'Brak odbioru') return;
            datesString.split(', ').forEach(dateStr => {
                const [day, month, year] = dateStr.split('.');
                const d = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
                const key = `${year}-${month}`;
                if (!byMonth[key]) byMonth[key] = [];
                byMonth[key].push({ date: d, dateStr, type: wasteType, isPast: d < today });
            });
        });

        // Sort entries by month key, then sort dates within each month
        return Object.entries(byMonth)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, items]) => {
                const [y, m] = key.split('-');
                items.sort((a, b) => a.date.getTime() - b.date.getTime());
                return { label: `${MONTHS_PL[parseInt(m) - 1]} ${y}`, items };
            });
    }, [mappedTown]);

    const [next, ...later] = upcomingDays;

    return (
        <div className="space-y-6">
            {next ? (
                <>
                    {/* Najbliższy wywóz — wartość jak na kaflu „Wywóz” pulpitu */}
                    <section aria-label="Najbliższy wywóz" className="flex flex-col items-start">
                        <Tag as="h2">Najbliższy wywóz</Tag>
                        <div className="w-full border-t-2 border-tv-blue bg-tv-panel px-4 pb-4 pt-3 lg:px-5">
                            <p className="font-cond tabular text-[34px] font-extrabold leading-[1.05] text-white lg:text-[40px]">
                                {dayWord(dateIn(next.days))}
                                {next.days <= 1 && (
                                    <span className="ml-3 text-[20px] text-tv-muted lg:text-[22px]">{next.date.slice(0, 5)}</span>
                                )}
                            </p>
                            <ul className="mt-2 space-y-1 text-[16px] font-semibold text-white">
                                {next.types.map(type => <li key={type}><WasteType type={type} /></li>)}
                            </ul>
                            <p className="mt-2 text-[15px] text-tv-muted">
                                {mappedTown}{next.days > 1 && <> · {inDays(next.days)}</>}
                            </p>
                        </div>
                    </section>

                    {later.length > 0 && (
                        <section aria-label="Kolejne terminy">
                            <Tag as="h2" tone="paper">Kolejne terminy</Tag>
                            <ul className="grid grid-cols-1 gap-px border-t-2 border-tv-paper bg-tv-seam">
                                {later.map(day => (
                                    <li key={day.date} className="flex gap-4 bg-tv-panel px-4 py-3">
                                        <span className="flex w-24 shrink-0 flex-col">
                                            <span className="font-cond tabular text-[22px] font-extrabold leading-none text-white">
                                                {dayWord(dateIn(day.days))}
                                            </span>
                                            <span className="tabular mt-1 text-[13px] text-tv-muted">{inDays(day.days)}</span>
                                        </span>
                                        <span className="min-w-0 flex-1 space-y-1 text-[16px] font-semibold text-white">
                                            {day.types.map(type => <WasteType key={type} type={type} />)}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    )}
                </>
            ) : (
                <Notice>Brak zaplanowanych odbiorów w najbliższym czasie.</Notice>
            )}

            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-tv-muted">
                <span>Dane na rok 2026</span>
                <span className="inline-flex items-center gap-1">
                    <CheckCircle2 size={14} className="text-tv-green" aria-hidden />
                    Aktualne
                </span>
            </p>

            {/* Pełny harmonogram rozwija się NA STRONIE — do 11.10.2026 był modalem,
                a lista terminów nie wymaga przerwania ani zamkniętego fokusu */}
            <section aria-label="Pełny harmonogram 2026">
                <button
                    onClick={() => setFullOpen(o => !o)}
                    aria-expanded={fullOpen}
                    aria-controls="waste-full"
                    className="font-cond inline-flex min-h-[52px] w-full items-center justify-center gap-2 bg-tv-blue px-4 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] sm:w-auto"
                >
                    Pełny harmonogram
                    {fullOpen ? <ChevronUp size={18} aria-hidden /> : <ChevronDown size={18} aria-hidden />}
                </button>

                {fullOpen && (
                    <div id="waste-full" className="mt-4 space-y-5">
                        <p className="text-[15px] text-tv-muted">
                            Pełny harmonogram 2026 · miejscowość: <span className="font-semibold text-tv-paper">{mappedTown}</span>
                        </p>
                        {fullSchedule.length === 0 && (
                            <Notice>Brak danych dla tej miejscowości.</Notice>
                        )}
                        {fullSchedule.map(({ label, items }) => (
                            <div key={label}>
                                <Tag as="h3" tone="seam">{label}</Tag>
                                <ul className="grid grid-cols-1 gap-px border-t border-tv-seam bg-tv-seam">
                                    {items.map((item, i) => (
                                        <li key={i} className="flex min-h-[44px] items-center gap-4 bg-tv-panel px-4 py-2 text-[15px]">
                                            <span className={`tabular w-14 shrink-0 font-semibold ${item.isPast ? 'text-tv-muted' : 'text-white'}`}>
                                                {item.dateStr.slice(0, 5)}
                                            </span>
                                            <span className={item.isPast ? '' : 'text-tv-paper'}>
                                                <WasteType type={item.type} muted={item.isPast} />
                                            </span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                        <p className="text-[13px] text-tv-muted">Pozycje wyszarzone = daty już minione</p>
                    </div>
                )}
            </section>
        </div>
    );
};

export default WasteWidget;
