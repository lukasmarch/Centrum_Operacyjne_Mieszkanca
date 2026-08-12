import React, { useMemo, useState } from 'react';
import { Clapperboard, MapPin, ExternalLink } from 'lucide-react';
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
        <span className="flex h-full w-full items-center justify-center bg-gradient-to-br from-violet-600/40 to-purple-950">
            <Clapperboard size={26} className="text-white/40" aria-hidden />
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
        <div className="mx-auto max-w-5xl px-4 py-6 lg:py-10">
            <header>
                <h1 className="text-3xl font-extrabold tracking-tight text-white lg:text-4xl">Kino</h1>
                <p className="mt-2 flex items-center gap-1.5 text-sm text-neutral-400">
                    <MapPin size={14} aria-hidden className="text-violet-400" />
                    {cinemaName} — najbliższe kino dla mieszkańców gminy Rybno
                </p>
            </header>

            {loading && <p className="mt-8 text-sm text-neutral-500">Sprawdzam repertuar…</p>}

            {!loading && !days.length && (
                <p className="mt-8 rounded-2xl border border-white/10 bg-[#0d1117] p-5 text-sm text-neutral-400">
                    Kino nie podało jeszcze repertuaru na najbliższe dni.
                </p>
            )}

            <div className="mt-6 space-y-6">
                {days.map(day => (
                    <section key={day.label}>
                        <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-neutral-500">
                            {day.label}
                        </h2>
                        {/* Dwie kolumny na desktopie: wiersz z plakatem 64 px
                            i jednym tytułem ciągnął się na całą szerokość strony,
                            zostawiając dwie trzecie pustego pola po prawej */}
                        <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                            {day.items.map(({ movie, at }) => (
                                <li
                                    key={`${movie.title}-${at.getTime()}`}
                                    className="flex items-stretch gap-4 rounded-2xl border border-white/10 bg-[#0d1117] p-4"
                                >
                                    <span className="h-[96px] w-[64px] shrink-0 overflow-hidden rounded-xl border border-white/10 bg-white/5">
                                        <Poster movie={movie} />
                                    </span>
                                    <span className="flex min-w-0 flex-1 flex-col justify-center">
                                        <span className="text-lg font-black leading-none text-white">
                                            {at.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' })}
                                        </span>
                                        <span className="mt-1.5 text-base font-semibold leading-snug text-neutral-100">
                                            {movie.title}
                                        </span>
                                        {movie.link && (
                                            <a
                                                href={movie.link}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="mt-1.5 inline-flex items-center gap-1 self-start text-[13px] font-semibold text-violet-300 hover:text-violet-200"
                                            >
                                                Bilety i szczegóły
                                                <ExternalLink size={12} aria-hidden />
                                            </a>
                                        )}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    </section>
                ))}
            </div>
        </div>
    );
};

export default CinemaPage;
