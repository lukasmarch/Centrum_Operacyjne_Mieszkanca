import React, { useState } from 'react';
import { Clapperboard, ChevronRight } from 'lucide-react';
import { Tag } from './tv';
import { useCinema } from '../../src/hooks/useCinema';

interface CinemaCardProps {
    onClick: () => void;
}

const DAYS = ['w niedzielę', 'w poniedziałek', 'we wtorek', 'w środę', 'w czwartek', 'w piątek', 'w sobotę'];

/**
 * „Co obejrzeć" — jeden film, ten najbliższy w czasie, z plakatem.
 *
 * Plakat jest tu po coś: lista tytułów bez okładek nie zatrzymuje wzroku,
 * a kino to jedyna rubryka w tym serwisie, w której obraz JEST treścią —
 * po plakacie poznaje się gatunek szybciej niż po nazwie.
 *
 * Kafel znika, gdy nie ma seansu przed nami. Pusty kafel „brak repertuaru"
 * uczy, że w tym miejscu zwykle nic nie ma, i przestaje być klikany.
 */
const CinemaCard: React.FC<CinemaCardProps> = ({ onClick }) => {
    const { next, cinemaName, loading } = useCinema();
    const [posterFailed, setPosterFailed] = useState(false);

    if (loading || !next) return null;

    const { movie, show } = next;
    const now = new Date();
    const isToday = show.at.toDateString() === now.toDateString();
    const tomorrow = new Date(now);
    tomorrow.setDate(now.getDate() + 1);
    const isTomorrow = show.at.toDateString() === tomorrow.toDateString();

    const when = isToday ? 'dziś' : isTomorrow ? 'jutro' : DAYS[show.at.getDay()];
    const time = show.at.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' });

    return (
        <section aria-label="Kino" className="flex flex-col">
            <Tag as="h2">{cinemaName}</Tag>
            <button
                onClick={onClick}
                className="group flex flex-1 items-stretch gap-4 border-t-2 border-tv-blue bg-tv-panel p-4 text-left transition-colors hover:bg-tv-panel2 lg:p-5"
            >
                {/* Plakat 2:3 — proporcja, w której plakaty powstają; zdjęcie niesie
                    własny kolor, interfejs wokół niego milknie */}
                <span className="relative h-[108px] w-[72px] shrink-0 overflow-hidden bg-tv-panel2 lg:h-[132px] lg:w-[88px]">
                    {movie.posterUrl && !posterFailed ? (
                        <img
                            src={movie.posterUrl}
                            alt={`Plakat filmu ${movie.title}`}
                            loading="lazy"
                            onError={() => setPosterFailed(true)}
                            className="h-full w-full object-cover"
                        />
                    ) : (
                        <span className="flex h-full w-full items-center justify-center">
                            <Clapperboard size={24} className="text-tv-muted" aria-hidden />
                        </span>
                    )}
                </span>
                <span className="flex min-w-0 flex-1 flex-col justify-center">
                    <span className="font-cond tabular text-[24px] font-extrabold leading-none text-white">
                        {when} {time}
                    </span>
                    <span className="mt-1.5 line-clamp-2 text-[16px] font-semibold leading-snug text-[#d7dbe8]">
                        {movie.title}
                    </span>
                    <span className="mt-1 inline-flex items-center gap-1 text-[15px] font-bold text-tv-bluesoft group-hover:text-white">
                        Repertuar <ChevronRight size={16} aria-hidden />
                    </span>
                </span>
            </button>
        </section>
    );
};

export default CinemaCard;
