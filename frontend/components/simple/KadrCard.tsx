import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Image as ImageIcon } from 'lucide-react';
import { PHOTO_POSTS } from '../../src/data/photoPosts';
import { Tag } from './tv';

/* Weekend wyszedł z tej karty 11.10.2026 (przegląd końcowy): zdjęcie i kalendarz
   to dwie niezwiązane rzeczy, a stopka w karcie zdjęcia była trudna do znalezienia.
   Stoi teraz obok kina jako `WeekendCard`. */
interface KadrCardProps {}

/**
 * „Gmina w kadrze" — własne zdjęcia z podpisem, przewijane jak galeria.
 *
 * Fundamentem jest rubryka, którą redakcja kontroluje sama (kalendarz wydarzeń
 * bywa pusty tygodniami). Od 19.10.2026 to galeria: przewijanie palcem na
 * telefonie (scroll-snap), strzałki < > na komputerze i kropki, które mówią,
 * ile jest zdjęć i na którym stoi czytelnik.
 *
 * ⚠️ Zdjęcie NIE jest przyciskiem — wcześniej kliknięcie w fotografię przenosiło
 * do kalendarza, czego nikt się nie spodziewa.
 * ⚠️ Kadr 16:10, a pliki w `public/simple/kadr/` są PRZYCIĘTE do 16:10 z logo
 * RybnoLive nałożonym PO przycięciu (prawy dolny róg). object-cover na nieprzyciętym
 * pliku ucinałby logo wbudowane w zdjęcie; object-contain zostawiał puste pasy po bokach.
 */
const KadrCard: React.FC<KadrCardProps> = () => {
    const posts = PHOTO_POSTS;
    const track = useRef<HTMLDivElement>(null);
    const [index, setIndex] = useState(0);
    const [failed, setFailed] = useState<Record<number, boolean>>({});

    const post = posts[index] ?? null;
    const dateLabel = post
        ? new Date(post.date).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })
        : null;

    const goTo = useCallback((i: number) => {
        const el = track.current;
        if (!el) return;
        const next = Math.max(0, Math.min(posts.length - 1, i));
        el.scrollTo({ left: next * el.clientWidth, behavior: 'smooth' });
    }, [posts.length]);

    // Indeks z pozycji przewijania — działa tak samo dla palca, strzałek i klawiatury.
    useEffect(() => {
        const el = track.current;
        if (!el) return;
        const onScroll = () => {
            const i = Math.round(el.scrollLeft / Math.max(1, el.clientWidth));
            setIndex((prev) => (prev === i ? prev : i));
        };
        el.addEventListener('scroll', onScroll, { passive: true });
        return () => el.removeEventListener('scroll', onScroll);
    }, []);

    // Strzałki bez tła: sama kreska z cieniem, czytelna i na jasnym, i na ciemnym niebie.
    const arrow =
        'absolute top-1/2 z-10 flex h-12 w-11 -translate-y-1/2 items-center justify-center text-white/80 ' +
        'drop-shadow-[0_1px_3px_rgba(0,0,0,0.7)] transition hover:text-white ' +
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-white disabled:pointer-events-none disabled:opacity-0';

    return (
        <section aria-label="Gmina w kadrze" className="flex flex-col">
            <Tag as="h2">Gmina w kadrze</Tag>
            <div className="flex flex-1 flex-col bg-tv-panel">
                {posts.length === 0 ? (
                    <div className="flex aspect-[16/10] w-full flex-col items-center justify-center gap-2 bg-tv-panel2 text-tv-muted">
                        <ImageIcon size={32} aria-hidden />
                        <span className="text-[14px]">własne zdjęcia gminy</span>
                    </div>
                ) : (
                    <div className="relative w-full shrink-0 bg-tv-panel2">
                        <div
                            ref={track}
                            role="group"
                            aria-roledescription="karuzela"
                            aria-label="Zdjęcia z gminy"
                            tabIndex={0}
                            onKeyDown={(e) => {
                                if (e.key === 'ArrowLeft') { e.preventDefault(); goTo(index - 1); }
                                if (e.key === 'ArrowRight') { e.preventDefault(); goTo(index + 1); }
                            }}
                            className="flex aspect-[16/10] w-full snap-x snap-mandatory overflow-x-auto scroll-smooth [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
                        >
                            {posts.map((p, i) => (
                                <div
                                    key={p.image}
                                    role="group"
                                    aria-roledescription="slajd"
                                    aria-label={`${i + 1} z ${posts.length}`}
                                    className="h-full w-full shrink-0 snap-center"
                                >
                                    {failed[i] ? (
                                        <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-tv-muted">
                                            <ImageIcon size={32} aria-hidden />
                                            <span className="text-[14px]">nie udało się wczytać zdjęcia</span>
                                        </div>
                                    ) : (
                                        <img
                                            src={p.image}
                                            alt={p.title}
                                            loading={i === 0 ? 'eager' : 'lazy'}
                                            draggable={false}
                                            onError={() => setFailed((f) => ({ ...f, [i]: true }))}
                                            className="h-full w-full select-none object-cover"
                                        />
                                    )}
                                </div>
                            ))}
                        </div>

                        {posts.length > 1 && (
                            <>
                                <button
                                    type="button"
                                    aria-label="Poprzednie zdjęcie"
                                    disabled={index === 0}
                                    onClick={() => goTo(index - 1)}
                                    className={`${arrow} left-0`}
                                >
                                    <ChevronLeft size={34} strokeWidth={2.25} aria-hidden />
                                </button>
                                <button
                                    type="button"
                                    aria-label="Następne zdjęcie"
                                    disabled={index === posts.length - 1}
                                    onClick={() => goTo(index + 1)}
                                    className={`${arrow} right-0`}
                                >
                                    <ChevronRight size={34} strokeWidth={2.25} aria-hidden />
                                </button>
                                <span
                                    aria-hidden
                                    className="absolute left-3 top-2 text-[13px] font-semibold text-white/85 drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)]"
                                >
                                    {index + 1} / {posts.length}
                                </span>
                            </>
                        )}
                    </div>
                )}

                {posts.length > 1 && (
                    <div className="flex flex-wrap items-center justify-center gap-x-1 px-3 pt-1" role="tablist" aria-label="Wybór zdjęcia">
                        {posts.map((p, i) => (
                            <button
                                key={p.image}
                                type="button"
                                role="tab"
                                aria-selected={i === index}
                                aria-label={`Zdjęcie ${i + 1} z ${posts.length}`}
                                onClick={() => goTo(i)}
                                // pole dotyku 24 px, widoczna kropka mniejsza — łatwo trafić palcem
                                className="flex h-6 w-6 items-center justify-center"
                            >
                                <span
                                    className={`block rounded-full transition-all ${
                                        i === index ? 'h-3 w-3 bg-tv-blue' : 'h-2 w-2 bg-tv-blue opacity-40'
                                    }`}
                                />
                            </button>
                        ))}
                    </div>
                )}

                <div className="flex flex-1 flex-col px-4 pb-4 pt-2 lg:px-5">
                    <h3 className="font-cond text-[21px] font-extrabold leading-snug text-white">
                        {post ? post.title : 'Zdjęcia z gminy'}
                    </h3>
                    <p className="mt-1 text-[15px] leading-relaxed text-[#d7dbe8]">
                        {post
                            ? post.description
                            : 'Wkrótce pojawią się tu kadry z gminy — z opisem tego, co na nich widać.'}
                    </p>
                    {(dateLabel || post?.credit) && (
                        <p className="mt-1 text-[14px] text-tv-muted">
                            {[dateLabel, post?.credit && `fot. ${post.credit}`].filter(Boolean).join(' · ')}
                        </p>
                    )}
                </div>
            </div>
        </section>
    );
};

export default KadrCard;
