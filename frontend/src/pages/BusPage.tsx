import React from 'react';
import { ArrowLeft } from 'lucide-react';
import { AppSection } from '../../types';
import BusTrackerWidget from '../../components/BusTrackerWidget';

/**
 * Autobus Rybno–Działdowo: rozkład, mapa i pozycja kursu na żywo.
 * Cel „rozwiń" z karty na stronie głównej — sama karta mówi tylko,
 * czy autobus jedzie i o której najbliższy.
 */
const BusPage: React.FC<{ onNavigate: (section: AppSection) => void }> = ({ onNavigate }) => (
    <div className="mx-auto max-w-4xl px-4 py-6 lg:py-10">
        <button
            onClick={() => onNavigate('dashboard')}
            className="mb-5 flex min-h-[44px] items-center gap-1.5 text-sm font-medium text-neutral-400 transition-colors hover:text-neutral-200"
        >
            <ArrowLeft size={16} aria-hidden />
            Wróć na stronę główną
        </button>

        <h1 className="text-2xl lg:text-3xl font-bold text-white">Autobus Rybno – Działdowo</h1>
        <p className="mt-1 text-sm text-neutral-400">Rozkład jazdy, przystanki i pozycja kursu na żywo</p>

        <div className="mt-6 rounded-2xl border border-white/10 bg-[#0d1117] overflow-hidden">
            <BusTrackerWidget />
        </div>
    </div>
);

export default BusPage;
