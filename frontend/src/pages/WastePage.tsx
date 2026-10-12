import React, { useState } from 'react';
import { AppSection } from '../../types';
import { useAuth } from '../context/AuthContext';
import { useWasteSchedule } from '../hooks/useWasteSchedule';
import { resolveWasteTown, rememberWasteTown, wasteTowns } from '../utils/wasteTown';
import WasteWidget from '../../components/WasteWidget';
import { Notice, PageHead, Select } from '../../components/simple/tv';

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
        <div className="max-w-3xl space-y-6">
            <PageHead title="Harmonogram wywozu odpadów" sub="Gmina Rybno — wszystkie miejscowości i frakcje" />

            <label className="block">
                <span className="text-[15px] font-semibold text-tv-paper">Twoja miejscowość</span>
                <Select value={town} onChange={e => chooseTown(e.target.value)} className="mt-2">
                    {!town && <option value="" disabled>Wybierz miejscowość…</option>}
                    {towns.map(name => <option key={name} value={name}>{name}</option>)}
                </Select>
                <span className="mt-2 block text-[15px] leading-snug text-tv-muted">
                    Rybno ma dwa rejony wywozu (R1 i R2) — terminy różnią się o tydzień.
                </span>
            </label>

            {town ? (
                <WasteWidget events={events} town={town} />
            ) : (
                <Notice>Wybierz miejscowość, a pokażemy najbliższe terminy wywozu.</Notice>
            )}
        </div>
    );
};

export default WastePage;
