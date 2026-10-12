import React from 'react';
import { ChevronRight } from 'lucide-react';
import { Tag } from './tv';

interface WeekendCardProps {
    /** Pierwsze wydarzenie weekendu (z godziną) albo `null`, gdy kalendarz jest pusty */
    subtitle: string | null;
    onOpenEvents: () => void;
}

/**
 * „W ten weekend” — wyjęte ze stopki karty zdjęcia (11.10.2026). Stoi obok kina,
 * bo odpowiada na to samo pytanie: co robić w wolny dzień.
 *
 * Pusty kalendarz mówimy wprost, bez obietnicy „daj znać” — za tamtym zdaniem
 * nie stał żaden formularz (zasada: każda obietnica ma pokrycie w kodzie).
 */
const WeekendCard: React.FC<WeekendCardProps> = ({ subtitle, onOpenEvents }) => (
    <section aria-label="W ten weekend" className="flex flex-col">
        <Tag as="h2">W ten weekend</Tag>
        <button
            onClick={onOpenEvents}
            className="group flex flex-col items-start bg-tv-panel px-4 pb-1 pt-3 text-left transition-colors hover:bg-tv-panel2 lg:px-5"
        >
            <span className="text-[16px] font-semibold leading-snug text-white">
                {subtitle ?? 'W kalendarzu na weekend nic jeszcze nie ma.'}
            </span>
            <span className="inline-flex min-h-[44px] items-center gap-1 text-[15px] font-bold text-tv-bluesoft group-hover:text-white">
                Kalendarz wydarzeń <ChevronRight size={16} aria-hidden />
            </span>
        </button>
    </section>
);

export default WeekendCard;
