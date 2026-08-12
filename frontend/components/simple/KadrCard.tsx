import React, { useState } from 'react';
import { Image as ImageIcon, CalendarDays, ArrowRight } from 'lucide-react';
import { PHOTO_POSTS } from '../../src/data/photoPosts';

interface KadrCardProps {
    /** Co się dzieje w najbliższy weekend — z kalendarza wydarzeń */
    weekendSubtitle: string;
    /** Czy w najbliższy weekend cokolwiek jest — decyduje o brzmieniu stopki */
    hasWeekendEvents: boolean;
    onOpenEvents: () => void;
}

/**
 * „Rybno w kadrze" — własne zdjęcie z podpisem, a pod nim weekend.
 *
 * Kolejność jest odwrócona względem poprzedniej wersji i to jest cała zmiana:
 * wcześniej fundamentem karty był kalendarz wydarzeń, a zdjęcie ozdobą. Kalendarz
 * w gminie wiejskiej bywa pusty tygodniami, więc karta przez pół roku pokazywała
 * „Kino, koncerty i atrakcje w okolicy" — zdanie, które nie mówi nic. Teraz
 * fundamentem jest rubryka, którą redakcja kontroluje sama, a wydarzenia są
 * dopiskiem, który pojawia się, kiedy naprawdę coś jest.
 *
 * ⚠️ Zdjęcie NIE jest przyciskiem. Wcześniej kliknięcie w fotografię przenosiło
 * do kalendarza wydarzeń, czego nikt się nie spodziewa. Klikalna jest wyłącznie
 * stopka z wydarzeniami — i tylko ona prowadzi do kalendarza.
 */
const KadrCard: React.FC<KadrCardProps> = ({ weekendSubtitle, hasWeekendEvents, onOpenEvents }) => {
    const post = PHOTO_POSTS[0] ?? null;
    const [imageOk, setImageOk] = useState(true);

    const dateLabel = post
        ? new Date(post.date).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })
        : null;

    return (
        <section
            aria-label="Rybno w kadrze"
            className="flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0d1117]"
        >
            <div className="relative h-44 w-full shrink-0 bg-gradient-to-br from-[#101a33] to-[#0d1117] lg:h-56">
                {post && imageOk ? (
                    <img
                        src={post.image}
                        alt=""
                        loading="lazy"
                        onError={() => setImageOk(false)}
                        className="h-full w-full object-cover"
                    />
                ) : (
                    <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-blue-300/50">
                        <ImageIcon size={32} aria-hidden />
                        <span className="text-xs">własne zdjęcie okolicy</span>
                    </div>
                )}
            </div>

            <div className="flex flex-1 flex-col p-5">
                <p className="flex flex-wrap items-center gap-x-2 text-[11px] font-bold uppercase tracking-wider text-blue-300">
                    Rybno w kadrze
                    {dateLabel && (
                        <span className="font-medium normal-case tracking-normal text-neutral-500">
                            {dateLabel}
                        </span>
                    )}
                </p>

                <h3 className="mt-1.5 text-lg font-bold leading-snug text-white">
                    {post ? post.title : 'Zdjęcia z gminy'}
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-neutral-400">
                    {post
                        ? post.description
                        : 'Wkrótce pojawią się tu kadry z gminy — z opisem tego, co na nich widać.'}
                </p>
                {post?.credit && (
                    <p className="mt-1 text-xs text-neutral-600">fot. {post.credit}</p>
                )}

                {/* Weekend jako stopka, nie jako treść nadrzędna. Gdy nic nie ma,
                    mówimy to wprost i pytamy — dziura zamienia się w zaproszenie,
                    a nie w zdanie-wypełniacz o „atrakcjach w okolicy" */}
                <button
                    onClick={onOpenEvents}
                    className="group mt-4 flex min-h-[44px] w-full items-center gap-3 border-t border-white/5 pt-4 text-left"
                >
                    <CalendarDays size={18} className="shrink-0 text-amber-400" aria-hidden />
                    <span className="min-w-0 flex-1">
                        <span className="block text-[13px] font-bold uppercase tracking-wider text-neutral-500">
                            W ten weekend
                        </span>
                        <span className="mt-0.5 block text-sm text-neutral-300">
                            {hasWeekendEvents
                                ? weekendSubtitle
                                : 'Nikt nic nie zgłosił. Organizujesz coś? Daj znać.'}
                        </span>
                    </span>
                    <ArrowRight
                        size={16}
                        aria-hidden
                        className="shrink-0 text-neutral-600 transition-colors group-hover:text-neutral-300"
                    />
                </button>
            </div>
        </section>
    );
};

export default KadrCard;
