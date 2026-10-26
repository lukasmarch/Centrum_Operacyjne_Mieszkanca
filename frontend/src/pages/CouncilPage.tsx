import React, { useState } from 'react';
import { track } from '../services/analytics';
import { Play, ExternalLink, ChevronDown } from 'lucide-react';
import { Notice, PageHead, Skeleton, Tag } from '../../components/simple/tv';
import {
    useCouncilSessions,
    useCouncilDetails,
    CouncilPoint,
    CouncilResolution,
} from '../hooks/useCouncil';

/**
 * Skróty obrad Rady Gminy — rejestr, nie strumień wiadomości.
 *
 * Układ jest listą sesji z rozwijanym skrótem, a nie osobnym adresem na sesję:
 * sesji jest ~10 w roku, więc paginacja i routing per sesja byłyby maszynerią
 * do obsługi jednego ekranu. Rozwinięcie dociąga punkty osobnym zapytaniem
 * (`useCouncilDetails`), bo na liście i tak się nie mieszczą.
 *
 * **Znacznik czasu jest tu najważniejszym elementem, nie ozdobą.** Cała
 * wiarygodność skrótu opiera się na tym, że każde zdanie da się sprawdzić
 * w nagraniu w dziesięć sekund — dlatego znacznik jest przyciskiem prowadzącym
 * do minuty, a nie szarym tekstem obok tytułu.
 */

const MONTHS = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca',
    'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];

/** „24 czerwca 2026" — data, którą mieszkaniec rozpozna, nie ISO. */
function dateLabel(iso: string | null): string {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    if (!y || !m || !d) return iso;
    return `${d} ${MONTHS[m - 1]} ${y}`;
}

/** „00:26:52" → „26:52”. Godzina zerowa niczego nie mówi, a zjada miejsce. */
function shortStamp(stamp?: string | null): string {
    if (!stamp) return '';
    const parts = stamp.split(':');
    if (parts.length === 3 && parts[0] === '00') return `${parts[1]}:${parts[2]}`;
    return stamp;
}

/**
 * Znacznik czasu otwierający nagranie w konkretnej minucie.
 *
 * Klik jest mierzony, bo to była CAŁA obietnica rolki z 28.08 („klikasz i nagranie
 * otwiera się dokładnie w tym miejscu"). Bez pomiaru nie wiadomo, czy ktokolwiek
 * z tego skorzystał — a to rozstrzyga, czy znaczniki w skrócie mają sens.
 */
const StampLink: React.FC<{ stamp?: string | null; url?: string | null }> = ({ stamp, url }) => {
    if (!stamp) return null;
    const label = shortStamp(stamp);
    if (!url) {
        return <span className="tabular shrink-0 text-[13px] text-tv-muted">{label}</span>;
    }
    // Znacznik to przycisk 44 px, nie szary tekst — patrz komentarz nad listą
    return (
        <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            title="Otwórz nagranie w tej minucie"
            onClick={() => track('session_stamp_click', { section: 'council', meta: { stamp: label } })}
            className="font-cond tabular inline-flex min-h-[44px] shrink-0 items-center gap-1.5 bg-tv-panel2 px-3 text-[15px] font-extrabold text-tv-bluesoft transition-colors hover:bg-tv-blue hover:text-white"
        >
            <Play size={12} aria-hidden className="fill-current" />
            {label}
        </a>
    );
};

const Point: React.FC<{ point: CouncilPoint }> = ({ point }) => (
    <li className="py-4 first:pt-1">
        <div className="flex items-start justify-between gap-3">
            <h4 className="pt-2 text-[17px] font-semibold leading-snug text-white">{point.title}</h4>
            <StampLink stamp={point.timestamp} url={point.watch_url} />
        </div>

        <p className="mt-1.5 max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">{point.description}</p>

        {point.quote && (
            <blockquote className="mt-3 max-w-[70ch] bg-tv-panel2 px-4 py-3 text-[15px] leading-relaxed text-white">
                „{point.quote}”
                {point.speaker && (
                    <footer className="mt-1 text-[13px] text-tv-muted">
                        — {point.speaker}
                    </footer>
                )}
            </blockquote>
        )}
    </li>
);

const Resolution: React.FC<{ resolution: CouncilResolution }> = ({ resolution }) => (
    <li className="flex items-start justify-between gap-3 py-2">
        <span className="min-w-0 pt-2.5 text-[15px] leading-snug text-[#d7dbe8]">
            {resolution.number && (
                <span className="tabular mr-1.5 font-bold text-white">{resolution.number}</span>
            )}
            {resolution.subject}
            {resolution.outcome && (
                <span className="ml-1.5 text-tv-muted">— {resolution.outcome}</span>
            )}
        </span>
        <StampLink stamp={resolution.timestamp} url={resolution.watch_url} />
    </li>
);

const CouncilPage: React.FC = () => {
    const { sessions, failed, loading } = useCouncilSessions();
    const { details, pending, load } = useCouncilDetails();
    const [open, setOpen] = useState<number | null>(null);

    const toggle = (id: number) => {
        setOpen(current => (current === id ? null : id));
        load(id);
    };

    return (
        <div className="max-w-4xl space-y-6 lg:space-y-8">
            {/* Podtytuł mówi, CO tu jest (podsumowanie najważniejszych spraw),
                a nie jak powstało. Skąd się bierze skrót, wyjaśnia jedno zdanie
                pod spodem — wcześniejsza ramka „Jak powstaje ten skrót" zajmowała
                pół ekranu i odsuwała pierwszą sesję poniżej zgięcia. */}
            <div>
                <PageHead
                    title="Sesje Rady Gminy"
                    sub="Podsumowanie obrad — najważniejsze sprawy z każdej sesji"
                />
                <p className="mt-3 max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">
                    Przy każdym temacie stoi minuta nagrania — jak rozdziały na YouTube.
                    Klikasz znacznik i nagranie otwiera się dokładnie w tym miejscu.
                </p>
            </div>

            {loading && (
                <div aria-label="Sprawdzam rejestr obrad…" className="space-y-px">
                    <Skeleton className="h-8 w-32" />
                    <Skeleton className="h-44" />
                </div>
            )}

            {failed && (
                <Notice tone="warn" role="alert">
                    Nie udało się pobrać skrótów obrad. Spróbuj odświeżyć stronę.
                </Notice>
            )}

            {!loading && !failed && sessions?.length === 0 && (
                <Notice>
                    Nie ma tu jeszcze żadnego skrótu. Pierwszy pojawi się po najbliższej sesji
                    Rady Gminy — terminy posiedzeń zbieramy w kalendarzu wydarzeń.
                </Notice>
            )}

            <div className="space-y-6">
                {sessions?.map(session => {
                    const expanded = open === session.id;
                    const detail = details[session.id];
                    const summary = detail?.summary;

                    return (
                        <article key={session.id} className="flex flex-col">
                            {/* Plakietka z numerem sesji JEST nagłówkiem; data i czas
                                nagrania stoją pod tytułem, nie jako etykieta nad nim */}
                            <Tag as="h2">{session.session_number ? `${session.session_number} sesja` : 'Sesja Rady'}</Tag>
                            <div className="border-t-2 border-tv-blue bg-tv-panel px-4 pb-4 pt-3 lg:px-5">
                                <h3 className="font-cond text-[22px] font-extrabold leading-snug text-white lg:text-[26px]">
                                    {session.headline || session.title}
                                </h3>
                                <p className="tabular mt-1 text-[14px] font-bold text-tv-paper">
                                    {dateLabel(session.session_date)}
                                    {session.duration_min && (
                                        <span className="font-normal text-tv-muted"> · {session.duration_min} min nagrania</span>
                                    )}
                                </p>

                                {session.lead && (
                                    <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">
                                        {session.lead}
                                    </p>
                                )}

                                <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
                                    <button
                                        type="button"
                                        onClick={() => toggle(session.id)}
                                        aria-expanded={expanded}
                                        className="font-cond inline-flex min-h-[44px] items-center gap-1.5 bg-tv-blue px-4 text-[15px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff]"
                                    >
                                        {expanded ? 'Zwiń skrót' : 'Zobacz, co ustalono'}
                                        <ChevronDown
                                            size={16}
                                            aria-hidden
                                            className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
                                        />
                                    </button>

                                    {session.video_url && (
                                        <a
                                            href={session.video_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex min-h-[44px] items-center gap-1.5 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline"
                                        >
                                            Całe nagranie obrad
                                            <ExternalLink size={14} aria-hidden />
                                        </a>
                                    )}
                                </div>
                            </div>

                            {expanded && (
                                <div className="border-t border-tv-seam bg-tv-panel px-4 pb-5 pt-4 lg:px-5">
                                    {!detail && pending === session.id && (
                                        <p className="text-[15px] text-tv-muted">Wczytuję skrót…</p>
                                    )}

                                    {summary?.points?.length ? (
                                        <ul className="divide-y divide-tv-seam">
                                            {summary.points.map((point, i) => (
                                                <Point key={`${point.timestamp}-${i}`} point={point} />
                                            ))}
                                        </ul>
                                    ) : null}

                                    {summary?.resolutions?.length ? (
                                        <section className="mt-5 flex flex-col">
                                            <h4 className="flex"><Tag tone="paper">Uchwały poddane pod głosowanie</Tag></h4>
                                            <ul className="divide-y divide-tv-seam border-t border-tv-paper">
                                                {summary.resolutions.map((resolution, i) => (
                                                    <Resolution key={`${resolution.subject}-${i}`} resolution={resolution} />
                                                ))}
                                            </ul>
                                        </section>
                                    ) : null}

                                    {detail && (
                                        <p className="mt-5 max-w-[70ch] text-[13px] leading-relaxed text-tv-muted">
                                            Skrót powstał z zapisu całego nagrania obrad.
                                            {' '}
                                            <a
                                                href={session.video_url ?? session.page_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="font-bold text-tv-bluesoft underline underline-offset-4 hover:text-white"
                                            >
                                                Nagranie na kanale YouTube Gminy Rybno
                                            </a>
                                            {' · '}
                                            Protokół z sesji publikuje Biuletyn Informacji Publicznej.
                                        </p>
                                    )}
                                </div>
                            )}
                        </article>
                    );
                })}
            </div>
        </div>
    );
};

export default CouncilPage;
