import React, { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { AppSection } from '../../types';
import { useAuth } from '../context/AuthContext';
import { useWasteSchedule } from '../hooks/useWasteSchedule';
import { resolveWasteTown, rememberWasteTown, wasteTowns } from '../utils/wasteTown';
import WasteWidget from '../../components/WasteWidget';

/**
 * Harmonogram wywozu odpadów — cel „rozwiń" z karty na stronie głównej.
 *
 * Miejscowość da się zmienić na miejscu: mieszkaniec Żabin nie musi zakładać
 * konta, żeby sprawdzić swój termin, a to najczęstsze pytanie w gminie
 * (i fraza z zerową konkurencją w wyszukiwarce).
 */
const WastePage: React.FC<{ onNavigate: (section: AppSection) => void }> = ({ onNavigate }) => {
    const { user } = useAuth();
    const towns = wasteTowns();
    // Miejscowość z profilu bywa nazwą, której harmonogram nie zna pod tym kluczem
    // („Rybno" dzieli się na rejony R1/R2). Do 11.10.2026 brak dopasowania dawał
    // po cichu R1 (audyt F-039) — dziś pusty wybór i prośba o wskazanie rejonu.
    // Wybór zapamiętujemy: strona główna pokaże potem właściwy termin
    const [town, setTown] = useState<string>(() => resolveWasteTown(user?.location) ?? '');
    const events = useWasteSchedule(town || null);
    const chooseTown = (value: string) => {
        setTown(value);
        if (value) rememberWasteTown(value);
    };

    return (
        <div className="mx-auto max-w-3xl px-4 py-6 lg:py-10">
            <button
                onClick={() => onNavigate('dashboard')}
                className="mb-5 flex min-h-[44px] items-center gap-1.5 text-sm font-medium text-neutral-400 transition-colors hover:text-neutral-200"
            >
                <ArrowLeft size={16} aria-hidden />
                Wróć na stronę główną
            </button>

            <h1 className="text-2xl lg:text-3xl font-bold text-white">Harmonogram wywozu odpadów</h1>
            <p className="mt-1 text-sm text-neutral-400">Gmina Rybno — wszystkie miejscowości i frakcje</p>

            <label className="mt-6 block">
                <span className="text-xs font-bold uppercase tracking-widest text-neutral-500">Twoja miejscowość</span>
                <select
                    value={town}
                    onChange={e => chooseTown(e.target.value)}
                    className="mt-2 min-h-[56px] w-full rounded-xl border border-white/10 bg-[#0d1117] px-4 text-base text-white outline-none transition-colors focus:border-blue-500/60"
                >
                    {!town && <option value="" disabled>Wybierz miejscowość…</option>}
                    {towns.map(name => <option key={name} value={name}>{name}</option>)}
                </select>
                <span className="mt-2 block text-sm text-neutral-400">
                    Rybno ma dwa rejony wywozu (R1 i R2) — terminy różnią się o tydzień.
                </span>
            </label>

            {town ? (
                <div className="mt-6 rounded-2xl border border-white/10 bg-[#0d1117]">
                    <WasteWidget events={events} town={town} />
                </div>
            ) : (
                <p className="mt-6 rounded-2xl border border-white/10 bg-[#0d1117] p-5 text-base text-neutral-300">
                    Wybierz miejscowość, a pokażemy najbliższe terminy wywozu.
                </p>
            )}
        </div>
    );
};

export default WastePage;
