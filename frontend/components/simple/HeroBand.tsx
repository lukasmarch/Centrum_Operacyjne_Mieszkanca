import React, { useState } from 'react';
import { CalendarDays } from 'lucide-react';
import { useAuth } from '../../src/context/AuthContext';
import { getNameDays, getHoliday } from '../../src/utils/calendarUtils';

/**
 * Pasmo powitalne — pierwsze, co widzi wchodzący.
 *
 * Zadanie: w jednym spojrzeniu powiedzieć, GDZIE ktoś wylądował. Wcześniej górę
 * strony otwierał sam tekst na płaskim tle i nie zatrzymywał wzroku; z drugiej
 * strony pełnoekranowe hero z animowaną kulą (121 klatek JPG) zostało wycięte
 * 11.08.2026, bo ważyło 456 kB i spychało treść pod krawędź ekranu. To jest
 * rozwiązanie pośrednie: jeden kadr, jedno pasmo, treść zaraz pod nim.
 *
 * Hasło, niebieska kreska pod nim i pigułka „na żywo" są **cytatem z materiałów
 * kampanii** (`public/og-image.jpg`), nie ozdobnikiem — mieszkaniec, który widział
 * post na Facebooku, ma poznać to samo miejsce.
 *
 * ⚠️ Czego tu NIE ma i dlaczego: ramki i fotografii kuli z kampanii. Obramowana
 * karta robiła z góry strony osobne pudełko odcięte od reszty, a każde zdjęcie ma
 * prostokąt — przy szerokości telefonu kula wchodziła w hasło i była przycinana
 * krawędzią karty. Zostały dwie miękkie plamy światła, które po prostu gasną
 * w tle strony: nie mają krawędzi, więc nie ma czego przyciąć, i ważą zero.
 */

/**
 * Zdjęcie gminy, gdy będzie: wystarczy wrzucić plik, układ się nie zmienia.
 * Kadr poziomy, raczej ciemny, z zapasem po lewej — tam stoi hasło.
 */
const PHOTO_SRC = '/simple/rybno-hero.jpg';

interface HeroBandProps {
    onOpenCalendar: () => void;
}

const HeroBand: React.FC<HeroBandProps> = ({ onOpenCalendar }) => {
    const { user } = useAuth();
    const [hasPhoto, setHasPhoto] = useState(true);

    const now = new Date();
    const firstName = user?.full_name?.trim().split(/\s+/)[0];

    // Wielka litera tylko na początku — CSS `capitalize` dałby „11 Sierpnia"
    const rawDate = now.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' });
    const dateLabel = rawDate.charAt(0).toUpperCase() + rawDate.slice(1);

    const nameDays = getNameDays(now);
    const holiday = getHoliday(now);

    return (
        <section aria-label="RybnoLive — serwis gminy Rybno" className="relative">
            {/* ——— tło ———
                BEZ ramki i bez własnego tła: pudełko z obwódką odcinało górę od
                reszty strony i przycinało to, co w nim leżało. Tu nie ma krawędzi,
                więc nie ma czego przyciąć — poświata po prostu gaśnie w tle strony.
                Z tego samego powodu odpadło zdjęcie kuli z kampanii: fotografia
                zawsze ma prostokąt, a przy szerokości telefonu wchodziła w tekst. */}
            <div
                className="pointer-events-none absolute -top-24 left-1/2 h-[calc(100%+6rem)] w-screen -translate-x-1/2 overflow-hidden"
                aria-hidden
            >
                {hasPhoto && (
                    <>
                        {/* Zdjęcie idzie na PEŁNĄ szerokość okna i sięga za górny
                            pasek. Gdy siedziało w obrysie kolumny, miało widoczny
                            prostokąt — czyli dokładnie to, co odrzuciliśmy przy kuli.
                            Boczne krawędzie znikają poza ekranem, górna i dolna
                            są wygaszane gradientem, więc zdjęcie nigdzie się
                            „nie kończy", tylko przechodzi w tło strony */}
                        <img
                            src={PHOTO_SRC}
                            alt=""
                            onError={() => setHasPhoto(false)}
                            className="h-full w-full object-cover opacity-90"
                        />
                        {/* Czytelność nie może zależeć od tego, co jest na zdjęciu:
                            lewa strona — tam stoi hasło — jest gaszona najmocniej */}
                        <div className="absolute inset-0 bg-gradient-to-r from-[#05080f] via-[#05080f]/85 to-[#05080f]/35 sm:via-[#05080f]/70 sm:to-[#05080f]/20" />
                        <div className="absolute inset-0 bg-[linear-gradient(to_bottom,#05080f_0%,rgba(5,8,15,0.22)_30%,rgba(5,8,15,0.35)_58%,#05080f_100%)]" />
                    </>
                )}

                {/* Poświata marki — dwie miękkie plamy, żadnych krawędzi.
                    Na telefonie mniejsze i bliżej rogu, żeby nie kładły się
                    pod hasłem i nie zabierały mu kontrastu. */}
                {!hasPhoto && (
                    <>
                        <div className="absolute -top-8 right-[-18%] h-64 w-64 rounded-full bg-[#2563eb]/35 blur-[90px] sm:h-[26rem] sm:w-[26rem] sm:right-[-8%] sm:blur-[120px]" />
                        <div className="absolute top-16 right-[-6%] h-40 w-40 rounded-full bg-[#22d3ee]/18 blur-[70px] sm:h-64 sm:w-64 sm:right-[4%] sm:blur-[100px]" />
                        {/* Trzecia plama siedzi pod samym hasłem: bez niej lewa
                            strona była płaska, a „Na żywo." nie miało w co świecić */}
                        <div className="absolute left-0 top-24 h-40 w-72 rounded-full bg-[#3a81f6]/10 blur-[80px] sm:h-56 sm:w-[28rem]" />
                    </>
                )}
            </div>

            {/* ——— treść ——— */}
            <div className="relative flex flex-col gap-5 pb-1 pt-1 lg:flex-row lg:items-start lg:justify-between lg:gap-10 lg:pt-3">
                <div className="min-w-0 animate-in fade-in slide-in-from-bottom-2 duration-700 motion-reduce:animate-none">
                    <span className="inline-flex items-center gap-2 rounded-full border border-blue-400/30 bg-blue-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-blue-200">
                        <span className="relative flex h-1.5 w-1.5">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70 motion-reduce:animate-none" />
                            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
                        </span>
                        na żywo
                    </span>

                    {user ? (
                        <h1 className="mt-3.5 text-3xl font-extrabold leading-[1.05] tracking-tight text-white lg:text-[2.75rem]">
                            Cześć, {firstName}!
                        </h1>
                    ) : (
                        // Dwa wiersze, nie jeden: tak hasło stoi na wszystkich
                        // materiałach kampanii i tak ma ciężar nagłówka, a nie
                        // podpisu. „Na żywo." niesie kolor marki i poświatę
                        <h1 className="mt-3.5 text-[2.15rem] font-extrabold leading-[0.98] tracking-tight sm:text-5xl lg:text-[3.5rem]">
                            <span className="block text-white">Twoja gmina.</span>
                            <span
                                className="block"
                                style={{ color: '#5b9cf6', filter: 'drop-shadow(0 0 24px rgba(91,156,246,0.35))' }}
                            >
                                Na żywo.
                            </span>
                        </h1>
                    )}

                    {/* Kreska wprost z karty kampanii — jedyny ozdobnik, na jaki
                        to pasmo sobie pozwala */}
                    <span className="mt-4 block h-[3px] w-12 rounded-full bg-blue-500" />

                    <p className="mt-3.5 max-w-[46ch] text-[15px] leading-relaxed text-neutral-300 lg:text-base">
                        {user
                            ? 'Wiadomości, alerty, pogoda i wydarzenia z gminy Rybno — wszystko w jednym miejscu.'
                            : (
                                <>
                                    Wiadomości, alerty, pogoda i&nbsp;wydarzenia z&nbsp;gminy Rybno —{' '}
                                    <span className="font-semibold text-white">wszystko w&nbsp;jednym miejscu.</span>
                                </>
                            )}
                    </p>
                </div>

                {/* Data i imieniny: własna płytka, nie luźny tekst pod hasłem.
                    Na telefonie schodzi pod spód całym blokiem — wcześniej wchodziła
                    między hasło a zdanie i rozrywała nagłówek na dwie części */}
                <button
                    onClick={onOpenCalendar}
                    aria-label="Otwórz kalendarz wydarzeń"
                    // Bez obwódki i bez tła: skoro pasmo przestało być pudełkiem,
                    // druga ramka na górze byłaby jedynym boksem na całej sekcji
                    // i ściągałaby uwagę z hasła
                    className="group flex shrink-0 items-center gap-3 self-start text-left lg:pt-1"
                >
                    <span className="min-w-0">
                        <span className="block text-[10px] font-bold uppercase tracking-[0.18em] text-neutral-500">
                            Dziś
                        </span>
                        <span className="block text-sm font-bold text-white lg:text-base">{dateLabel}</span>
                        {holiday && <span className="block text-xs text-amber-400">{holiday}</span>}
                        {nameDays && (
                            <span className="block text-[11px] text-neutral-500">Imieniny: {nameDays}</span>
                        )}
                    </span>
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-[#0d1117] transition-colors group-hover:border-white/25 group-hover:bg-[#141c2b]">
                        <CalendarDays size={18} className="text-neutral-300" aria-hidden />
                    </span>
                </button>
            </div>
        </section>
    );
};

export default HeroBand;
