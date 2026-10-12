import React from 'react';
import { ChevronRight, LucideIcon } from 'lucide-react';

interface TodayCardProps {
    icon: LucideIcon;
    /** Klasy koloru ikony i jej tła — kolory semantyczne kategorii z DESIGN.md */
    iconClass: string;
    iconBgClass: string;
    title: string;
    subtitle: string;
    onClick: () => void;
}

/**
 * Pojedyncza karta „3 rzeczy na dziś".
 * Mobile: wiersz z ikoną po lewej. Desktop: karta z ikoną nad tytułem.
 * Ta sama treść, inny układ — desktop nie dostaje nic ekstra (brief §3.3).
 */
const TodayCard: React.FC<TodayCardProps> = ({ icon: Icon, iconClass, iconBgClass, title, subtitle, onClick }) => (
    <button
        onClick={onClick}
        className="flex w-full min-h-[72px] items-center gap-4 rounded-2xl border border-white/10 bg-[#0d1117] p-4 text-left transition-colors hover:border-white/20 hover:bg-white/[0.04] lg:min-h-0 lg:flex-col lg:items-start lg:gap-3 lg:p-5"
    >
        <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${iconBgClass}`}>
            <Icon size={20} className={iconClass} aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
            <span className="block text-base font-semibold text-white">{title}</span>
            {/* Bez `truncate`: „21° zachmurzenie umiarkowane · powietrze bardzo czyste"
                urywało się na mobile w połowie słowa — druga linia jest tańsza niż zagadka */}
            <span className="mt-0.5 block text-sm text-neutral-400">{subtitle}</span>
        </span>
        <ChevronRight size={18} className="shrink-0 text-neutral-600 lg:hidden" aria-hidden />
    </button>
);

export default TodayCard;
