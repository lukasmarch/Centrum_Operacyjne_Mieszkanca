import React, { useEffect, useState } from 'react';
import { Store, Phone, Clock, Tag, ArrowRight, ExternalLink } from 'lucide-react';
import {
    fetchCatalog, fetchActiveAnnouncements, trackBusinessImpression, getAssetUrl, promotableCards,
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
/**
 * Najwyżej dwa kafle z każdego rodzaju. Sekcja ma zapraszać, nie zajmować
 * ekranu — strona główna należy do treści gminnej, reklama jest gościem.
 */
const MAX_PER_KIND = 2;

/**
 * Rotacja wyróżnień: który dzień roku, taka wycinka listy.
 *
 * Problem, który to rozwiązuje: dziesięciu klientów płaci po 49 zł za to samo
 * „wyróżnienie", a miejsca są dwa. Bez rotacji dwie firmy dostają wszystko,
 * a osiem płaci za nic — i pierwsza, która to zauważy, ma rację, rezygnując.
 * Przy rotacji dziennej każdy dostaje równy udział dni, a obietnica sprzedażowa
 * daje się napisać uczciwie: *stale* na górze katalogu, *rotacyjnie* na stronie
 * głównej.
 *
 * Dzień, nie losowanie: ta sama firma ma stać przez całą dobę, żeby dało się
 * powiedzieć „byłeś widoczny we wtorek". Losowanie przy każdym wejściu jest
 * niemierzalne i wygląda na usterkę, gdy odświeżysz stronę.
 */
function rotateByDay<T>(items: T[], take: number): T[] {
    if (items.length <= take) return items;
    const dayOfYear = Math.floor(
        (Date.now() - new Date(new Date().getFullYear(), 0, 0).getTime()) / 86_400_000,
    );
    const start = (dayOfYear * take) % items.length;
    return Array.from({ length: take }, (_, i) => items[(start + i) % items.length]);
}

const AdBoard: React.FC<AdBoardProps> = ({ onOpenBusinesses }) => {
    const { user } = useAuth();
    // Obietnica „brak reklam" należy do KAŻDEGO planu płatnego, nie tylko Premium
    // — `business` kosztuje pięć razy więcej i widziałby ogłoszenia konkurencji.
    // Ta sama bramka stoi w `NewsFeed` (ogłoszenia firm) i w newsletterze.
    const hidesAds = user?.tier === 'premium' || user?.tier === 'business';

    const [firms, setFirms] = useState<CatalogCard[]>([]);
    const [ads, setAds] = useState<ActiveAnnouncement[]>([]);
    const [firmsTotal, setFirmsTotal] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (hidesAds) {
            setLoading(false);
            return;
        }
        let cancelled = false;
        Promise.allSettled([fetchCatalog(), fetchActiveAnnouncements(8)])
            .then(([catalog, announcements]) => {
                if (cancelled) return;
                if (catalog.status === 'fulfilled') {
                    const promotable = promotableCards(catalog.value);
                    setFirmsTotal(promotable.length);
                    setFirms(rotateByDay(promotable, MAX_PER_KIND));
                }
                if (announcements.status === 'fulfilled') {
                    setAds(rotateByDay(announcements.value, MAX_PER_KIND));
                }
            })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [hidesAds]);

    if (hidesAds || loading) return null;

    const isEmpty = !firms.length && !ads.length;
    const hidden = Math.max(0, firmsTotal - firms.length);

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
                            onClick={() => { trackBusinessImpression(firm.id); onOpenBusinesses(); }}
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
                    {/* Liczba mówi wprost, że rotacja istnieje — firma, która dziś
                        nie stoi na stronie głównej, widzi, że nie zniknęła */}
                    {hidden > 0 ? `Wszystkie wyróżnione firmy (${firmsTotal})` : 'Wszystkie firmy z gminy'}
                    <ExternalLink size={14} aria-hidden />
                </button>
            )}
        </section>
    );
};

export default AdBoard;
