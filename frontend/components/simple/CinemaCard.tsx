import React, { useState } from 'react';
import { Clapperboard, ChevronRight } from 'lucide-react';
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
        <button
            onClick={onClick}
            className="group flex w-full items-stretch gap-4 overflow-hidden rounded-2xl border border-white/10 bg-[#0d1117] p-4 text-left transition-colors hover:border-white/20 hover:bg-white/[0.04] lg:p-5"
        >
            {/* Plakat w proporcji 2:3, czyli tej, w której plakaty powstają —
                kadrowanie do kwadratu ucina twarze i tytuł */}
            <span className="relative h-[92px] w-[62px] shrink-0 overflow-hidden rounded-xl border border-white/10 bg-white/5 lg:h-[116px] lg:w-[78px]">
                {movie.posterUrl && !posterFailed ? (
                    <img
                        src={movie.posterUrl}
                        alt=""
                        loading="lazy"
                        onError={() => setPosterFailed(true)}
                        className="h-full w-full object-cover"
                    />
                ) : (
                    <span className="flex h-full w-full items-center justify-center bg-gradient-to-br from-violet-600/40 to-purple-950">
                        <Clapperboard size={22} className="text-white/40" aria-hidden />
                    </span>
                )}
            </span>

            <span className="flex min-w-0 flex-1 flex-col justify-center">
                <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-violet-300">
                    <Clapperboard size={12} aria-hidden />
                    Co obejrzeć
                </span>
                <span className="mt-1 line-clamp-2 text-base font-semibold leading-snug text-white">
                    {movie.title}
                </span>
                <span className="mt-1 text-[13px] text-neutral-400">
                    <span className="font-semibold text-neutral-200">{when} o {time}</span>
                    {' · '}{cinemaName}
                </span>
            </span>

            <ChevronRight size={18} className="shrink-0 self-center text-neutral-600" aria-hidden />
        </button>
    );
};

export default CinemaCard;
