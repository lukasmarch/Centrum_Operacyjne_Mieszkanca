import React, { useState } from 'react';
import { Image as ImageIcon } from 'lucide-react';
import { PHOTO_POSTS } from '../../src/data/photoPosts';
import { Tag } from './tv';

/* Weekend wyszedł z tej karty 11.10.2026 (przegląd końcowy): zdjęcie i kalendarz
   to dwie niezwiązane rzeczy, a stopka w karcie zdjęcia była trudna do znalezienia.
   Stoi teraz obok kina jako `WeekendCard`. */
interface KadrCardProps {}

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
const KadrCard: React.FC<KadrCardProps> = () => {
    const post = PHOTO_POSTS[0] ?? null;
    const [imageOk, setImageOk] = useState(true);

    const dateLabel = post
        ? new Date(post.date).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })
        : null;

    return (
        <section aria-label="Rybno w kadrze" className="flex flex-col">
            <Tag as="h2">Rybno w kadrze</Tag>
            <div className="flex flex-1 flex-col bg-tv-panel">
                <div className="relative h-48 w-full shrink-0 bg-tv-panel2 lg:h-60">
                    {post && imageOk ? (
                        <img
                            src={post.image}
                            alt={post.title}
                            loading="lazy"
                            onError={() => setImageOk(false)}
                            className="h-full w-full object-cover"
                        />
                    ) : (
                        <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-tv-muted">
                            <ImageIcon size={32} aria-hidden />
                            <span className="text-[14px]">własne zdjęcie okolicy</span>
                        </div>
                    )}
                </div>

                <div className="flex flex-1 flex-col px-4 pb-4 pt-3 lg:px-5">
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
