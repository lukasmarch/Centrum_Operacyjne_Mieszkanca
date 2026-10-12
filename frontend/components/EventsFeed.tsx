import React, { useState, useMemo } from 'react';
import StaleDataNotice from './StaleDataNotice';
import { MapPin, CalendarPlus, ExternalLink } from 'lucide-react';
import { useMyVillage } from '../src/hooks/useMyVillage';
import { useEvents } from '../src/hooks/useEvents';
import { TimedEvent, endOf, isAllDay, phaseOf } from '../src/utils/eventTime';
import { Chip, Notice, PageHead, Skeleton, Tag, categoryGlyph, dayWord, hm } from './simple/tv';

/* ── Google Calendar ── */
// Wpis całodniowy idzie jako DZIEŃ (YYYYMMDD/następny dzień), nie jako
// 00:00–02:00 — tak wpadał do kalendarza mieszkańca do 11.10.2026 (audyt F-038).
// Koniec z `endOf`: ta sama reguła co kafle (podany koniec albo 2 h).
function generateGoogleCalendarUrl(event: TimedEvent): string {
    const start = new Date(event.date);
    let dates: string;
    if (isAllDay(event)) {
        const day = (d: Date) =>
            `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
        const next = new Date(start);
        next.setDate(next.getDate() + 1);
        dates = `${day(start)}/${day(next)}`;
    } else {
        const fmt = (d: Date) => d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
        dates = `${fmt(start)}/${fmt(endOf(event))}`;
    }
    const params = new URLSearchParams({
        action: 'TEMPLATE',
        text: event.title,
        dates,
        details: event.description || '',
        location: event.location || '',
    });
    return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

/* ── Dni jako sekcje ── */
// Do 11.10.2026 lista dzieliła się na MIESIĄCE, a datę niosła kostka w każdej
// karcie. W kalendarzu gminy pytanie brzmi „co jest dziś / jutro / w sobotę”,
// więc sekcją jest DZIEŃ, a jego plakietka („DZIŚ”, „JUTRO”, „SB 18.10”) jest
// nagłówkiem. Wydarzenie wielodniowe, które zaczęło się wcześniej i wciąż trwa,
// stoi pod „dziś” — tam go szukamy, a nie pod wczorajszą datą.
const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

function dayKeyOf(event: TimedEvent, todayStart: Date): number {
    const day = startOfDay(new Date(event.date));
    return Math.max(day.getTime(), todayStart.getTime());
}

/** Pierwsza wieś z gminy w miejscu albo tytule wydarzenia. */
function villageOf(event: TimedEvent, places: string[]): string | null {
    const hay = `${event.location ?? ''} ${event.title}`.toLowerCase();
    // Dłuższe nazwy najpierw — „Rybno” siedzi w „Gminie Rybno” i w wielu nazwach organizatorów
    return [...places].sort((a, b) => b.length - a.length).find(p => hay.includes(p.toLowerCase().slice(0, Math.max(4, p.length - 2)))) ?? null;
}

/** „za 10 dni” — odległość dnia od dziś; dziś/jutro mówi już plakietka. */
function distanceWord(day: Date): string | null {
    const diff = Math.round((startOfDay(day).getTime() - startOfDay(new Date()).getTime()) / 86_400_000);
    if (diff < 2) return null;
    return diff < 7 ? `za ${diff} dni` : diff < 14 ? 'za tydzień' : `za ${Math.round(diff / 7)} tyg.`;
}

const countWord = (n: number) =>
    n === 1 ? 'wydarzenie' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? 'wydarzenia' : 'wydarzeń';

/* ── Wiersz wydarzenia ── */
/**
 * Wiersz wydarzenia — układ pod telefon 375 px (audyt V13, F-043).
 *
 * Do 11.10.2026 w jednym wierszu stały: data, miniatura, treść i przycisk
 * „Google Cal”, więc na tytuł zostawało 54 px, a terminy i źródło miały
 * 7–11 px przy kontraście 1,9–2,5:1 — „kiedy” i „skąd” były nieczytelne
 * dla starszych mieszkańców. Do tego cała karta była linkiem z przyciskiem
 * w środku (zagnieżdżone elementy interaktywne).
 * Dziś: datę niesie plakietka dnia nad sekcją, a wiersz zaczyna się od
 * GODZINY — wartości wąskim krojem, jak na kaflach pulpitu. Obok treść
 * (miniatura dopiero od `sm`), pod nią źródło i „Dodaj do kalendarza”;
 * linkiem jest tytuł. Metadane ≥ 13 px.
 */
const EventRow: React.FC<{ event: TimedEvent; places: string[] }> = ({ event, places }) => {
    const d = new Date(event.date);
    const allDay = isAllDay(event);
    // Trwające = żółta plakietka (zapowiedź/kontekst), NIE czerwień — ta należy do awarii
    const ongoing = phaseOf(event) === 'ongoing';
    // Koniec pokazujemy tylko podany przez źródło; domyślne +3 h z `endOf`
    // to reguła ważności, a nie godzina, którą wolno wydrukować
    const end = event.endDate ? endOf(event) : null;
    // Wieś z gminy jako plakietka (krytyka 11.10: „Działdowo” i „Kopaniarze”
    // w tej samej szarej linii — nie było widać, co jest u nas)
    const village = villageOf(event, places);
    const Glyph = categoryGlyph(event.category);

    return (
        <article className="flex gap-3 bg-tv-panel p-3 sm:gap-4 sm:p-4">
            {/* Kolumna godziny: wartość, koniec, piktogram rodzaju i kalendarz */}
            <div className="flex w-[72px] shrink-0 flex-col items-start sm:w-24">
                {allDay ? (
                    <span className="font-cond text-[17px] font-extrabold uppercase leading-tight text-tv-paper">cały dzień</span>
                ) : (
                    <span className="font-cond tabular text-[26px] font-extrabold leading-none text-white">{hm(d)}</span>
                )}
                {end && (
                    <span className="tabular mt-1 text-[13px] leading-none text-tv-muted">do {hm(end)}</span>
                )}
                {ongoing && <Tag tone="yellow" className="mt-1.5">trwa</Tag>}
                <span className="mt-auto flex items-center gap-1 pt-2">
                    <Glyph size={20} strokeWidth={1.75} aria-hidden className="text-tv-muted" />
                    <a
                        href={generateGoogleCalendarUrl(event)}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Dodaj do kalendarza: ${event.title}`}
                        title="Dodaj do kalendarza Google"
                        className="flex h-11 w-11 items-center justify-center text-tv-bluesoft transition-colors hover:bg-tv-panel2 hover:text-white"
                    >
                        <CalendarPlus size={20} aria-hidden />
                    </a>
                </span>
            </div>

            <div className="min-w-0 flex-1">
                {village && <Tag tone="paper" className="mb-1">{village}</Tag>}
                {(event.category || event.location) && (
                    <p className="text-[13px] leading-snug text-tv-muted">
                        {event.category && <span className="font-bold text-tv-paper">{event.category}</span>}
                        {event.category && event.location && ' · '}
                        {event.location && (
                            <span className="inline-flex items-center gap-1">
                                <MapPin size={13} className="shrink-0" aria-hidden />
                                {event.location}
                            </span>
                        )}
                    </p>
                )}
                <h3 className="mt-0.5 text-[17px] font-semibold leading-snug text-white">
                    {event.externalUrl ? (
                        <a
                            href={event.externalUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group/t inline-block py-1 underline-offset-4 hover:underline"
                        >
                            {event.title}
                            <ExternalLink size={14} aria-hidden className="ml-1.5 inline-block align-[-1px] text-tv-muted group-hover/t:text-white" />
                            <span className="sr-only"> (otwiera się w nowej karcie)</span>
                        </a>
                    ) : event.title}
                </h3>
                {event.description && (
                    <p className="mt-0.5 line-clamp-2 max-w-[62ch] text-[15px] leading-snug text-[#d7dbe8]">{event.description}</p>
                )}
                {event.sourceName && (
                    <p className="mt-1 text-[13px] text-tv-muted">Źródło: {event.sourceName}</p>
                )}
            </div>

            {/* Prawdziwe zdjęcie tylko od `sm` — na telefonie zabierało tytułowi miejsce */}
            {event.imageUrl && (
                <div className="hidden h-20 w-20 shrink-0 overflow-hidden bg-tv-panel2 sm:block">
                    <img
                        src={event.imageUrl}
                        alt=""
                        loading="lazy"
                        className="h-full w-full object-cover"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                </div>
            )}
        </article>
    );
};

/* ── Main Component ── */

const EventsFeed: React.FC<{ initialCategory?: string }> = ({ initialCategory }) => {
    const { events: allEvents, loading, error, fetchedAt } = useEvents(100);
    // „Nadchodzące” bez tego, co już się skończyło (audyt F-038). API oddaje
    // wydarzenia od początku dzisiejszej doby — kafle strony głównej potrzebują
    // porannych, żeby powiedzieć „dziś już po wszystkim”. Koniec liczy `endOf`,
    // ta sama reguła co backend (`time_span.event_end`). `fetchedAt` w zależnościach:
    // lista przelicza się z każdym odświeżeniem, więc 10:00 nie wisi do wieczora
    const events = useMemo(
        () => (allEvents ? allEvents.filter(e => phaseOf(e) !== 'past') : null),
        [allEvents, fetchedAt],
    );
    const [activeCategory, setActiveCategory] = useState<string>(initialCategory || 'Wszystkie');
    const { places } = useMyVillage();

    const categoryCounts = useMemo(() => {
        if (!events) return {} as Record<string, number>;
        const counts: Record<string, number> = {};
        events.forEach(e => {
            const cat = e.category || 'Inne';
            counts[cat] = (counts[cat] || 0) + 1;
        });
        return counts;
    }, [events]);

    const sortedCategories = useMemo(() => {
        return Object.entries(categoryCounts)
            .sort((a, b) => (b[1] as number) - (a[1] as number))
            .map(([cat]) => cat);
    }, [categoryCounts]);


    // Filter & dedupe
    const filteredEvents = useMemo(() => {
        if (!events) return [];
        let filtered = events;
        if (activeCategory !== 'Wszystkie') {
            filtered = events.filter(e => e.category === activeCategory);
        }
        return filtered.filter((ev, i, arr) =>
            i === arr.findIndex(t =>
                t.title === ev.title &&
                new Date(t.date).toDateString() === new Date(ev.date).toDateString()
            )
        );
    }, [events, activeCategory]);

    // Sekcje po dniach (lokalna doba), w dniu — po godzinie
    const groupedEvents = useMemo(() => {
        const todayStart = startOfDay(new Date());
        const groups = new Map<number, TimedEvent[]>();
        filteredEvents.forEach(ev => {
            const key = dayKeyOf(ev, todayStart);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key)!.push(ev);
        });
        return [...groups.entries()]
            .sort(([a], [b]) => a - b)
            .map(([key, list]) => ({
                day: new Date(key),
                events: [...list].sort((a, b) => +new Date(a.date) - +new Date(b.date)),
            }));
    }, [filteredEvents, fetchedAt]);

    // Czy dziś i jutro są puste (po filtrze) — wtedy jedno zdanie nad listą
    const quietSoon = useMemo(() => {
        if (!groupedEvents.length) return false;
        const word = dayWord(groupedEvents[0].day);
        return word !== 'dziś' && word !== 'jutro';
    }, [groupedEvents]);

    if (loading) return (
        <div className="space-y-6" aria-busy="true">
            <PageHead title="Nadchodzące wydarzenia" sub="Wczytuję…" />
            <div className="flex gap-1.5">
                {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-11 w-24" />)}
            </div>
            <div className="grid grid-cols-1 gap-px bg-tv-seam">
                {[1, 2, 3].map(i => <Skeleton key={i} className="h-28" />)}
            </div>
        </div>
    );

    // Błąd bez żadnych danych — przy danych lista zostaje, a nad nią `StaleDataNotice`
    if (error && !events) return (
        <div className="space-y-6">
            <PageHead title="Nadchodzące wydarzenia" />
            <Notice tone="warn" role="alert">Nie udało się pobrać wydarzeń. Sprawdź połączenie i spróbuj za chwilę.</Notice>
        </div>
    );
    if (!events || events.length === 0) return (
        <div className="space-y-6">
            <PageHead title="Nadchodzące wydarzenia" />
            <Notice>Brak nadchodzących wydarzeń.</Notice>
        </div>
    );

    return (
        <div className="space-y-6 lg:space-y-8">
            <PageHead
                title="Nadchodzące wydarzenia"
                sub={<>
                    <span className="tabular">{filteredEvents.length}</span>
                    {activeCategory !== 'Wszystkie' && <> z <span className="tabular">{events.length}</span></>}
                    {' '}{countWord(filteredEvents.length)}
                    {activeCategory !== 'Wszystkie' && <> w kategorii „{activeCategory}”</>}, najbliższe pierwsze.
                </>}
            />
            {error && <StaleDataNotice fetchedAt={fetchedAt} />}

            {/* Filtry kategorii — kwadratowe, jak w Wiadomościach; kolor kategorii
                nie niesie stanu, więc go nie ma */}
            {/* Jeden rząd przewijany na telefonie, jak w Wiadomościach */}
            <div
                role="group"
                aria-label="Kategorie"
                className="no-scrollbar -mx-4 flex gap-1.5 overflow-x-auto px-4 md:-mx-8 md:px-8 lg:mx-0 lg:flex-wrap lg:overflow-visible lg:px-0"
            >
                <Chip active={activeCategory === 'Wszystkie'} onClick={() => setActiveCategory('Wszystkie')} count={events.length}>
                    Wszystkie
                </Chip>
                {sortedCategories.map(cat => (
                    <Chip
                        key={cat}
                        active={activeCategory === cat}
                        onClick={() => setActiveCategory(cat)}
                        count={categoryCounts[cat] || 0}
                    >
                        {cat}
                    </Chip>
                ))}
            </div>

            {/* Pusty „dziś i jutro” też jest odpowiedzią — lista bez tego zdania
                zaczynała się od dnia za tydzień, jakby był najbliższy */}
            {quietSoon && groupedEvents.length > 0 && (
                <p className="bg-tv-yellow px-4 py-2.5 text-[15px] leading-snug text-tv-ink">
                    <span className="font-bold">Dziś i jutro nic w kalendarzu.</span> Najbliższe: {dayWord(groupedEvents[0].day)}.
                </p>
            )}

            {/* ── Dni: plakietka dnia JEST nagłówkiem sekcji ── */}
            {filteredEvents.length === 0 ? (
                <Notice>Brak wydarzeń w kategorii „{activeCategory}”.</Notice>
            ) : (
                groupedEvents.map(({ day, events: dayEvents }) => {
                    const word = dayWord(day);
                    const isToday = word === 'dziś';
                    const fullDate = day.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' });
                    const far = distanceWord(day);
                    return (
                        <section key={day.getTime()} aria-label={fullDate}>
                            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                                <Tag as="h2" tone={isToday ? 'blue' : 'paper'} className="tabular">{word}</Tag>
                                {/* Plakietka ma już dzień i datę („ŚR 21.10”) — obok tylko odległość
                                    i liczba; pełna data zostaje dla czytnika ekranu (aria-label) */}
                                <span className="text-[14px] text-tv-muted">
                                    {far && <span className="font-semibold text-tv-paper">{far}</span>}
                                    {far && dayEvents.length > 1 && ' · '}
                                    {dayEvents.length > 1 && <><span className="tabular">{dayEvents.length}</span> {countWord(dayEvents.length)}</>}
                                </span>
                            </div>
                            <div className={`grid grid-cols-1 gap-px border-t-2 bg-tv-seam ${isToday ? 'border-tv-blue' : 'border-tv-paper'}`}>
                                {dayEvents.map(event => <EventRow key={event.id} event={event} places={places} />)}
                            </div>
                        </section>
                    );
                })
            )}
        </div>
    );
};

export default EventsFeed;
