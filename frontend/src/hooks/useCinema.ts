import { useEffect, useMemo, useState } from 'react';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Repertuar kina — tylko **Kino Działdowo**.
 *
 * ⚠️ Dlaczego bez Lubawy: `kino.lubawa.pl` pisze „Psi Patrol — **od 7 sierpnia**
 * godz. 13:00 i 15:00", a scraper zapisuje to jako jednorazowy seans dnia 7.08.
 * Film najpewniej gra dalej, ale w bazie wygląda na przeszły. Dopóki backend nie
 * odróżnia „gra od dnia X" od „gra dnia X", każdy pokaz Lubawy albo znika przy
 * filtrze przyszłości, albo podaje mieszkańcowi datę, której kino nie obiecywało.
 * Sprawdzone na produkcji 12.08.2026 — to nie awaria scrapera, tylko zapis źródła.
 *
 * ⚠️ Świadomie NIE używam `services/geminiService.fetchCinemaRepertoire`: przy
 * błędzie API podstawia zmyślony repertuar („Diuna: Część druga (Offline)").
 * Atrapa na stronie głównej gminy to nie jest łagodna awaria — to nieprawda
 * podana z pełnym przekonaniem.
 */

export interface CinemaShowtime {
    /** Moment seansu; `null`, gdy godziny nie dało się rozpoznać */
    at: Date;
    label: string;
}

export interface CinemaMovie {
    title: string;
    genre: string;
    posterUrl: string;
    rating: string;
    link?: string | null;
    /** Wyłącznie seanse jeszcze przed nami, od najbliższego */
    upcoming: CinemaShowtime[];
}

interface RawMovie {
    title: string;
    genre: string;
    time: string[];
    posterUrl: string;
    rating: string;
    link?: string | null;
}

/**
 * Backend podaje godziny jako „12.08 18:15" (z datą) albo „18:15" (dziś).
 * Rok jest domyślny — przy przełomie roku seans ze stycznia oglądany
 * w grudniu wypadłby o rok wstecz i zniknął jako „przeszły".
 */
function parseShowtime(raw: string, now: Date): Date | null {
    const withDate = raw.match(/^(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})$/);
    const timeOnly = raw.match(/^(\d{1,2}):(\d{2})$/);

    if (timeOnly) {
        const at = new Date(now);
        at.setHours(Number(timeOnly[1]), Number(timeOnly[2]), 0, 0);
        return at;
    }
    if (!withDate) return null;

    const [, day, month, hour, minute] = withDate.map(Number);
    const at = new Date(now.getFullYear(), month - 1, day, hour, minute, 0, 0);
    if (at.getTime() < now.getTime() - 30 * 24 * 3600 * 1000) {
        at.setFullYear(at.getFullYear() + 1);
    }
    return at;
}

export function useCinema() {
    const [movies, setMovies] = useState<CinemaMovie[] | null>(null);
    const [cinemaName, setCinemaName] = useState<string>('Kino Działdowo');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;

        fetch(`${API_URL}/cinema/repertoire?location=${encodeURIComponent('Działdowo')}`)
            .then(res => (res.ok ? res.json() : null))
            .then(data => {
                if (cancelled) return;
                if (!data?.movies) {
                    setMovies([]);
                    return;
                }
                setCinemaName(data.cinemaName || 'Kino Działdowo');

                const now = new Date();
                const parsed: CinemaMovie[] = (data.movies as RawMovie[]).map(movie => ({
                    title: movie.title,
                    genre: movie.genre,
                    posterUrl: movie.posterUrl,
                    rating: movie.rating,
                    link: movie.link,
                    upcoming: movie.time
                        .map(raw => {
                            const at = parseShowtime(raw, now);
                            return at ? { at, label: raw } : null;
                        })
                        .filter((s): s is CinemaShowtime => s !== null && s.at.getTime() >= now.getTime())
                        .sort((a, b) => a.at.getTime() - b.at.getTime()),
                }));

                // Film bez seansu przed nami zniknął z repertuaru — na stronie
                // gminy nie ma powodu wypisywać, co grało w zeszłym tygodniu
                setMovies(parsed.filter(m => m.upcoming.length > 0));
            })
            .catch(() => { if (!cancelled) setMovies([]); })
            .finally(() => { if (!cancelled) setLoading(false); });

        return () => { cancelled = true; };
    }, []);

    /** Najbliższy seans w ogóle — to on trafia na stronę główną */
    const next = useMemo(() => {
        if (!movies?.length) return null;
        return movies
            .map(movie => ({ movie, show: movie.upcoming[0] }))
            .sort((a, b) => a.show.at.getTime() - b.show.at.getTime())[0];
    }, [movies]);

    return { movies, next, cinemaName, loading };
}
