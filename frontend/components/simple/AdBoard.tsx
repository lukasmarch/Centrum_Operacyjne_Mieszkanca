import React, { useEffect, useState } from 'react';
import { Store, Phone, Clock, Tag, ArrowRight, ExternalLink } from 'lucide-react';
import {
    fetchCatalog, fetchActiveAnnouncements, trackBusinessView, getAssetUrl, promotableCards,
    CatalogCard, ActiveAnnouncement,
} from '../../src/services/businessApi';
import { useAuth } from '../../src/context/AuthContext';

interface AdBoardProps {
    onOpenBusinesses: () => void;
}

/**
 * Sekcja „Reklama" — WSZYSTKO, za co ktoś zapłacił, pod jednym nagłówkiem.
 *
 * Wcześniej płatne treści były rozsypane po dwóch miejscach: kafel „Polecane
 * w Rybnie" z wyróżnionymi wizytówkami (osierocony w wycofanym bento-panelu,
 * więc od 11.08 nie widział go nikt) i tablica `NoticeBoard` z ogłoszeniami firm,
 * która nosiła tytuł „Ogłoszenia z gminy" — czyli reklama podszywała się pod
 * komunikat gminny.
 *
 * Nazwa sekcji brzmi **Reklama**, nie „Lokalne firmy" ani „Polecane w Rybnie".
 * Decyzja Łukasza z 12.08.2026 i jest w niej rachunek: serwis żyje z zaufania,
 * a etykieta, która nazywa rzecz po imieniu, kosztuje mniej niż mieszkaniec,
 * który zorientuje się sam. Ogłoszenia mieszkańców i komunikaty sołtysów
 * dostaną osobną szynę („Ogłoszenia drobne") i NIGDY nie trafią tutaj.
 *
 * ⚠️ Premium ma w cenniku „brak reklam w feedzie" — cała sekcja nie renderuje
 * się dla tego planu. Odznaka „Polecane w Rybnie" w katalogu firm zostaje,
 * bo katalog to miejsce, do którego wchodzi się z własnej woli.
 */
const AdBoard: React.FC<AdBoardProps> = ({ onOpenBusinesses }) => {
    const { user } = useAuth();
    const hidesAds = user?.tier === 'premium';

    const [firms, setFirms] = useState<CatalogCard[]>([]);
    const [ads, setAds] = useState<ActiveAnnouncement[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (hidesAds) {
            setLoading(false);
            return;
        }
        let cancelled = false;
        Promise.allSettled([fetchCatalog(), fetchActiveAnnouncements(4)])
            .then(([catalog, announcements]) => {
                if (cancelled) return;
                if (catalog.status === 'fulfilled') setFirms(promotableCards(catalog.value).slice(0, 3));
                if (announcements.status === 'fulfilled') setAds(announcements.value.slice(0, 2));
            })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [hidesAds]);

    if (hidesAds || loading) return null;

    const isEmpty = !firms.length && !ads.length;

    return (
        <section aria-label="Reklama">
            <h2 className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-bold uppercase tracking-widest text-neutral-500">
                <Store size={13} className="text-amber-500" aria-hidden />
                Reklama
                <span className="font-medium normal-case tracking-normal text-neutral-600">
                    · firmy z gminy, które opłaciły wyróżnienie
                </span>
            </h2>

            {/*
              Pusta sekcja NIE znika, bo to jedyne miejsce, w którym przedsiębiorca
              dowiaduje się, że może tu być. To nie jest wypełniacz — to lejek
              i dziś jedyna droga sprzedaży planu Firma lokalna
            */}
            {isEmpty ? (
                <button
                    onClick={onOpenBusinesses}
                    className="group flex w-full items-center gap-4 rounded-2xl border border-dashed border-amber-500/25 bg-amber-500/[0.04] p-5 text-left transition-colors hover:border-amber-500/40"
                >
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-500/10">
                        <Store size={20} className="text-amber-400" aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                        <span className="block text-base font-semibold text-white">
                            Twoja firma może być tutaj
                        </span>
                        <span className="mt-0.5 block text-sm text-neutral-400">
                            Wizytówkę przejmiesz za darmo. Wyróżnienie na stronie głównej
                            i w katalogu jest w planie Firma lokalna.
                        </span>
                    </span>
                    <ArrowRight
                        size={18}
                        aria-hidden
                        className="shrink-0 text-neutral-600 transition-colors group-hover:text-amber-300"
                    />
                </button>
            ) : (
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 lg:gap-4">
                    {firms.map(firm => (
                        <button
                            key={firm.id}
                            onClick={() => { trackBusinessView(firm.id); onOpenBusinesses(); }}
                            className="flex items-start gap-3 rounded-2xl border border-amber-500/20 bg-amber-500/[0.05] p-4 text-left transition-colors hover:border-amber-500/35"
                        >
                            {firm.profile.logo_url ? (
                                <img
                                    src={getAssetUrl(firm.profile.logo_url)}
                                    alt=""
                                    loading="lazy"
                                    className="h-11 w-11 shrink-0 rounded-xl border border-white/10 object-cover"
                                />
                            ) : (
                                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-500/10">
                                    <Store size={18} className="text-amber-400" aria-hidden />
                                </span>
                            )}
                            <span className="min-w-0 flex-1">
                                <span className="block text-base font-semibold leading-snug text-white">
                                    {firm.nazwa}
                                </span>
                                {firm.profile.description && (
                                    <span className="mt-0.5 line-clamp-2 block text-sm text-neutral-400">
                                        {firm.profile.description}
                                    </span>
                                )}
                                <span className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[13px] text-neutral-500">
                                    {firm.profile.telefon && (
                                        <span className="inline-flex items-center gap-1">
                                            <Phone size={11} aria-hidden />{firm.profile.telefon}
                                        </span>
                                    )}
                                    {firm.profile.godziny && (
                                        <span className="inline-flex items-center gap-1">
                                            <Clock size={11} aria-hidden />{firm.profile.godziny}
                                        </span>
                                    )}
                                </span>
                            </span>
                        </button>
                    ))}

                    {ads.map(ad => (
                        <article
                            key={`ad-${ad.id}`}
                            className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.05] p-4"
                        >
                            <div className="flex items-start gap-3">
                                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-500/10">
                                    <Tag size={18} className="text-amber-400" aria-hidden />
                                </span>
                                <div className="min-w-0 flex-1">
                                    <p className="text-base font-semibold leading-snug text-white">{ad.title}</p>
                                    <p className="mt-0.5 text-sm leading-snug text-neutral-400">{ad.body}</p>
                                    <p className="mt-1.5 text-[13px] text-neutral-500">{ad.nazwa}</p>
                                </div>
                            </div>
                        </article>
                    ))}
                </div>
            )}

            {!isEmpty && (
                <button
                    onClick={onOpenBusinesses}
                    className="mt-3 flex min-h-[44px] items-center gap-1.5 text-sm font-semibold text-amber-400 transition-colors hover:text-amber-300"
                >
                    Wszystkie firmy z gminy
                    <ExternalLink size={14} aria-hidden />
                </button>
            )}
        </section>
    );
};

export default AdBoard;
