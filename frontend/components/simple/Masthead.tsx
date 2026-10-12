import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, MapPin, X } from 'lucide-react';
import { getNameDays, getHoliday } from '../../src/utils/calendarUtils';

/**
 * Główka pulpitu: dzień, imieniny i WIEŚ czytelnika.
 *
 * Zastąpiła `HeroBand` (11.10.2026). Hasło „Twoja gmina. Na żywo.” zajmowało
 * ~60% pierwszego ekranu telefonu, a każdy wchodzący przyszedł z naszego
 * posta i wie, gdzie jest. Pierwszy ekran należy do odpowiedzi: belka awarii
 * i plakietki „Na dziś” stoją teraz tuż pod tą jedną linią.
 *
 * Wybór wsi rozwija się NA MIEJSCU, nie w oknie modalnym: to jedna decyzja
 * z 22 możliwych, a lista przycisków pod ręką jest szybsza niż okno
 * zasłaniające to, co wybór za chwilę zmieni.
 *
 * To JEDYNE miejsce wsi na stronie. Górny pasek pokazywał do 11.10 osobno
 * „Konto: Żabiny · Zmień”, więc zalogowany widział dwie wsie naraz. Zalogowany
 * startuje od wsi z konta; inna to podgląd do końca wizyty (`useMyVillage`).
 */

interface MastheadProps {
    village: string | null;
    /** Wieś z konta; `null` dla gościa */
    accountVillage?: string | null;
    /** Zalogowany ogląda inną wieś niż swoją */
    isPreview?: boolean;
    /** Stała zmiana wsi konta — w profilu */
    onOpenProfile?: () => void;
    places: string[];
    onSelectVillage: (name: string | null) => void;
    /** Otwiera wybór z zewnątrz (np. z kafla odpadów albo belki) */
    pickerRequest?: number;
}

const Masthead: React.FC<MastheadProps> = ({
    village, accountVillage = null, isPreview = false, onOpenProfile, places, onSelectVillage, pickerRequest = 0,
}) => {
    const [open, setOpen] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (pickerRequest > 0) setOpen(true);
    }, [pickerRequest]);

    useEffect(() => {
        if (open) panelRef.current?.querySelector<HTMLButtonElement>('button[data-place]')?.focus();
    }, [open]);

    const now = new Date();
    // Wielka litera tylko na początku — CSS `capitalize` dałby „11 Października”
    const raw = now.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' });
    const dateLabel = raw.charAt(0).toUpperCase() + raw.slice(1);
    const nameDays = getNameDays(now);
    const holiday = getHoliday(now);

    const choose = (name: string | null) => {
        onSelectVillage(name);
        setOpen(false);
    };

    return (
        <section aria-label="Dziś w gminie Rybno" className="border-b border-tv-seam pb-3">
            <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
                <div className="min-w-0">
                    <h1 className="font-cond text-[22px] font-extrabold leading-tight text-white lg:text-[28px]">
                        {dateLabel}
                    </h1>
                    <p className="text-[15px] leading-snug text-tv-muted">
                        {holiday && <span className="font-semibold text-tv-yellow">{holiday} · </span>}
                        {nameDays ? `Imieniny: ${nameDays}` : 'Gmina Rybno'}
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                {isPreview && accountVillage && (
                    <button
                        onClick={() => choose(accountVillage)}
                        className="min-h-[44px] text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline"
                    >
                        Wróć do: {accountVillage}
                    </button>
                )}
                <button
                    onClick={() => setOpen(v => !v)}
                    aria-expanded={open}
                    aria-controls="village-picker"
                    className={`font-cond flex min-h-[44px] items-center gap-2 px-3.5 text-[17px] font-extrabold uppercase tracking-wide transition-colors ${
                        village && !isPreview
                            ? 'bg-tv-paper text-tv-ink hover:bg-white'
                            : 'bg-tv-yellow text-tv-ink hover:bg-[#ffe27a]'
                    }`}
                >
                    <MapPin size={17} aria-hidden />
                    {village ?? 'Wybierz swoją wieś'}
                    {isPreview && <span className="sr-only">(podgląd — nie Twoja wieś z konta)</span>}
                    <ChevronDown size={17} aria-hidden className={`transition-transform ${open ? 'rotate-180' : ''}`} />
                </button>
                </div>
            </div>

            {open && (
                <div
                    id="village-picker"
                    ref={panelRef}
                    className="mt-3 border border-tv-seam bg-tv-panel p-3"
                    onKeyDown={e => { if (e.key === 'Escape') setOpen(false); }}
                >
                    <div className="mb-2 flex items-start justify-between gap-3">
                        {accountVillage ? (
                            <p className="text-[15px] leading-snug text-tv-paper">
                                Twoja wieś z konta: <strong className="font-bold text-white">{accountVillage}</strong>.
                                Inną możesz podejrzeć do końca tej wizyty; na stałe zmienisz ją{' '}
                                {onOpenProfile ? (
                                    <button
                                        onClick={() => { setOpen(false); onOpenProfile(); }}
                                        className="font-bold text-tv-bluesoft underline underline-offset-4 hover:text-white"
                                    >
                                        w profilu
                                    </button>
                                ) : 'w profilu'}.
                            </p>
                        ) : (
                            <p className="text-[15px] leading-snug text-tv-paper">
                                W której wsi mieszkasz? Pokażemy awarie i wywóz dla niej. Wybór zostaje na tym urządzeniu.
                            </p>
                        )}
                        <button
                            onClick={() => setOpen(false)}
                            aria-label="Zamknij wybór wsi"
                            className="flex h-11 w-11 shrink-0 items-center justify-center text-tv-muted hover:text-white"
                        >
                            <X size={20} aria-hidden />
                        </button>
                    </div>
                    {places.length === 0 ? (
                        <p className="text-[15px] text-tv-muted">Nie udało się pobrać listy miejscowości. Spróbuj za chwilę.</p>
                    ) : (
                        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-6">
                            {places.map(name => (
                                <button
                                    key={name}
                                    data-place
                                    onClick={() => choose(name)}
                                    aria-pressed={name === village}
                                    className={`min-h-[48px] px-3 text-left text-[16px] font-semibold transition-colors ${
                                        name === village
                                            ? 'bg-tv-blue text-white'
                                            : 'bg-tv-panel2 text-tv-paper hover:bg-tv-seam'
                                    }`}
                                >
                                    {name}
                                    {name === accountVillage && (
                                        <span className={`block text-[13px] font-normal ${name === village ? 'text-white/80' : 'text-tv-muted'}`}>
                                            z konta
                                        </span>
                                    )}
                                </button>
                            ))}
                        </div>
                    )}
                    {village && !accountVillage && (
                        <button
                            onClick={() => choose(null)}
                            className="mt-2 min-h-[44px] text-[15px] font-semibold text-tv-muted underline underline-offset-4 hover:text-white"
                        >
                            Nie zapamiętuj wsi — pokazuj całą gminę
                        </button>
                    )}
                </div>
            )}
        </section>
    );
};

export default Masthead;
