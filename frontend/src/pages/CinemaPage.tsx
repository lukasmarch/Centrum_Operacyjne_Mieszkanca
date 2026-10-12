import React, { useMemo, useState } from 'react';
import { Clapperboard, ExternalLink } from 'lucide-react';
import { Notice, PageHead, Skeleton, Tag } from '../../components/simple/tv';
import { useCinema, CinemaMovie } from '../hooks/useCinema';

const DAY_NAMES = ['niedziela', 'poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota'];

/**
 * Repertuar kina — „w głąb" kafla „Co obejrzeć" ze strony głównej.
 *
 * Układ jest dniami, nie filmami: mieszkaniec planuje wieczór („co jest
 * w piątek?"), a nie ściga jeden tytuł. Ta sama kolejność co w kaflu:
 * najbliższe na górze.
 *
 * Kino Pokój w Lubawie świadomie nieobecne — patrz komentarz w `useCinema`.
 */

function dayKey(d: Date) {
    return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function dayLabel(d: Date, now: Date) {
    if (d.toDateString() === now.toDateString()) return 'Dziś';
    const tomorrow = new Date(now);
    tomorrow.setDate(now.getDate() + 1);
    if (d.toDateString() === tomorrow.toDateString()) return 'Jutro';
    const name = DAY_NAMES[d.getDay()];
    return `${name.charAt(0).toUpperCase()}${name.slice(1)} ${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`;
}

const Poster: React.FC<{ movie: CinemaMovie; className?: string }> = ({ movie, className = '' }) => {
    const [failed, setFailed] = useState(false);
    if (movie.posterUrl && !failed) {
        return (
            <img
                src={movie.posterUrl}
                alt=""
                loading="lazy"
                onError={() => setFailed(true)}
                className={`h-full w-full object-cover ${className}`}
            />
        );
    }
    return (
        <span className="flex h-full w-full items-center justify-center">
            <Clapperboard size={24} className="text-tv-muted" aria-hidden />
        </span>
    );
};

const CinemaPage: React.FC = () => {
    const { movies, cinemaName, loading } = useCinema();

    /** Dzień → lista (film, godzina). Jeden przebieg, bo filmów są jednostki */
    const days = useMemo(() => {
        if (!movies) return [];
        const now = new Date();
        const map = new Map<string, { date: Date; items: { movie: CinemaMovie; at: Date }[] }>();

        movies.forEach(movie => {
            movie.upcoming.forEach(show => {
                const key = dayKey(show.at);
                if (!map.has(key)) {
                    const date = new Date(show.at);
                    date.setHours(0, 0, 0, 0);
                    map.set(key, { date, items: [] });
                }
                map.get(key)!.items.push({ movie, at: show.at });
            });
        });

        return [...map.values()]
            .sort((a, b) => a.date.getTime() - b.date.getTime())
            .map(day => ({
                ...day,
                label: dayLabel(day.date, now),
                items: day.items.sort((a, b) => a.at.getTime() - b.at.getTime()),
            }));
    }, [movies]);

    return (
        <div className="max-w-5xl space-y-6 lg:space-y-8">
            <PageHead
                title="Kino"
                sub={<>{cinemaName} — najbliższe kino dla mieszkańców gminy Rybno</>}
            />

            {loading && (
                <div aria-label="Sprawdzam repertuar…" className="space-y-px">
                    <Skeleton className="h-8 w-24" />
                    <Skeleton className="h-36" />
                </div>
            )}

            {!loading && !days.length && (
                <Notice>Kino nie podało jeszcze repertuaru na najbliższe dni.</Notice>
            )}

            {days.map(day => (
                <section key={day.label} className="flex flex-col">
                    <Tag as="h2">{day.label}</Tag>
                    {/* Dwie kolumny na desktopie: wiersz z plakatem 64 px
                        i jednym tytułem ciągnął się na całą szerokość strony,
                        zostawiając dwie trzecie pustego pola po prawej */}
                    <ul className="grid grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-seam lg:grid-cols-2">
                        {day.items.map(({ movie, at }) => (
                            <li
                                key={`${movie.title}-${at.getTime()}`}
                                className="flex items-stretch gap-4 bg-tv-panel p-4"
                            >
                                {/* Plakat 2:3, kąty proste — obraz niesie własny kolor */}
                                <span className="h-[108px] w-[72px] shrink-0 overflow-hidden bg-tv-panel2">
                                    <Poster movie={movie} />
                                </span>
                                <span className="flex min-w-0 flex-1 flex-col justify-center">
                                    <span className="font-cond tabular text-[24px] font-extrabold leading-none text-white">
                                        {at.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' })}
                                    </span>
                                    <span className="mt-1.5 text-[17px] font-semibold leading-snug text-[#d7dbe8]">
                                        {movie.title}
                                    </span>
                                    {movie.link && (
                                        <a
                                            href={movie.link}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex min-h-[44px] items-center gap-1.5 self-start text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline"
                                        >
                                            Bilety i szczegóły
                                            <ExternalLink size={14} aria-hidden />
                                        </a>
                                    )}
                                </span>
                            </li>
                        ))}
                        {/* Nieparzysta liczba seansów zostawiłaby w siatce pole w kolorze
                            szwu — wypełniamy je tłem strony */}
                        {day.items.length % 2 === 1 && (
                            <li aria-hidden className="hidden bg-tv-ink lg:block" />
                        )}
                    </ul>
                </section>
            ))}
        </div>
    );
};

export default CinemaPage;
