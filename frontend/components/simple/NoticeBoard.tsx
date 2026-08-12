import React, { useEffect, useState } from 'react';
import { Megaphone, Phone } from 'lucide-react';
import { ActiveAnnouncement, fetchActiveAnnouncements } from '../../src/services/businessApi';
import { useAuth } from '../../src/context/AuthContext';

/**
 * Tablica ogłoszeń na stronie głównej.
 *
 * Docelowo dwa rodzaje wpisów pod jednym nagłówkiem: **komunikaty** sołtysów
 * i instytucji gminnych (bezpłatne, informacja publiczna) oraz **reklamy**
 * firm z planu „Firma lokalna". Dziś backend zwraca wyłącznie te drugie
 * (`business_announcements`), więc sekcja pokazuje na razie ogłoszenia firm.
 *
 * Dwie zasady, które muszą przetrwać rozbudowę:
 * 1. Reklama jest OZNACZONA i stoi poza wiadomościami — mieszkaniec ma wiedzieć,
 *    za co ktoś zapłacił. Serwis żyje z zaufania, nie z kliknięć.
 * 2. Premium ma w cenniku „brak reklam w feedzie", więc płatne wpisy do niego
 *    nie trafiają. Komunikaty sołtysów zostaną dla wszystkich — to nie reklama.
 */
const NoticeBoard: React.FC = () => {
    const { user } = useAuth();
    const [items, setItems] = useState<ActiveAnnouncement[]>([]);

    const hidesAds = user?.tier === 'premium';

    useEffect(() => {
        if (hidesAds) return;
        fetchActiveAnnouncements(4).then(setItems).catch(() => setItems([]));
    }, [hidesAds]);

    // Bez ogłoszeń nie ma pustej ramki — ta sama zasada co przy alercie i briefingu
    if (hidesAds || !items.length) return null;

    return (
        <section aria-label="Ogłoszenia z gminy">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-neutral-500">
                <Megaphone size={13} className="text-amber-500" aria-hidden />
                Ogłoszenia z gminy
                <span className="font-medium normal-case tracking-normal text-neutral-600">· materiał reklamowy</span>
            </h2>

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 lg:gap-4">
                {items.map(item => (
                    <article key={item.id} className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.05] p-4">
                        <div className="flex items-start justify-between gap-3">
                            <h3 className="text-base font-semibold text-white">{item.title}</h3>
                            {item.type === 'okazja' && item.valid_until && (
                                <span className="shrink-0 text-xs font-medium text-amber-400">
                                    do {new Date(item.valid_until).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })}
                                </span>
                            )}
                        </div>
                        <p className="mt-1 text-sm leading-relaxed text-neutral-400">{item.body}</p>
                        <p className="mt-2 flex flex-wrap items-center gap-x-2 text-xs text-neutral-500">
                            <span>{item.nazwa} · {item.miasto}</span>
                            {item.telefon && (
                                <a href={`tel:${item.telefon}`} className="inline-flex items-center gap-1 text-neutral-400 hover:text-neutral-200">
                                    <Phone size={11} aria-hidden />
                                    {item.telefon}
                                </a>
                            )}
                        </p>
                    </article>
                ))}
            </div>
        </section>
    );
};

export default NoticeBoard;
