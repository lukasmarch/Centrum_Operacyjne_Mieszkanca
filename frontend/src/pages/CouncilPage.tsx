import React, { useState } from 'react';
import { Landmark, Play, ExternalLink, ChevronDown, Gavel } from 'lucide-react';
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

const StampLink: React.FC<{ stamp?: string | null; url?: string | null }> = ({ stamp, url }) => {
    if (!stamp) return null;
    const label = shortStamp(stamp);
    if (!url) {
        return <span className="font-mono text-xs text-neutral-500">{label}</span>;
    }
    return (
        <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            title="Otwórz nagranie w tej minucie"
            className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-sky-400/30 bg-sky-400/10 px-2 py-1 font-mono text-xs font-semibold text-sky-300 transition-colors hover:border-sky-400/60 hover:bg-sky-400/20 hover:text-sky-200"
        >
            <Play size={10} aria-hidden className="fill-current" />
            {label}
        </a>
    );
};

const Point: React.FC<{ point: CouncilPoint }> = ({ point }) => (
    <li className="border-t border-white/10 py-5 first:border-t-0 first:pt-0">
        <div className="flex items-start justify-between gap-3">
            <h4 className="text-[15px] font-bold leading-snug text-white">{point.title}</h4>
            <StampLink stamp={point.timestamp} url={point.watch_url} />
        </div>

        <p className="mt-2 text-[14.5px] leading-relaxed text-neutral-300">{point.description}</p>

        {point.quote && (
            <blockquote className="mt-3 rounded-r-xl border-l-[3px] border-sky-500 bg-sky-500/5 px-4 py-2.5 text-[14px] leading-relaxed text-neutral-200">
                „{point.quote}”
                {point.speaker && (
                    <footer className="mt-1 text-xs font-medium not-italic text-neutral-500">
                        — {point.speaker}
                    </footer>
                )}
            </blockquote>
        )}
    </li>
);

const Resolution: React.FC<{ resolution: CouncilResolution }> = ({ resolution }) => (
    <li className="flex items-start justify-between gap-3 border-t border-white/5 py-2.5 first:border-t-0">
        <span className="min-w-0 text-[14px] leading-snug text-neutral-300">
            {resolution.number && (
                <span className="mr-1.5 font-semibold text-neutral-100">{resolution.number}</span>
            )}
            {resolution.subject}
            {resolution.outcome && (
                <span className="ml-1.5 text-neutral-500">— {resolution.outcome}</span>
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
        <div className="mx-auto max-w-4xl px-4 py-6 lg:py-10">
            {/* Podtytuł mówi, CO tu jest (podsumowanie najważniejszych spraw),
                a nie jak powstało. Skąd się bierze skrót, wyjaśnia jedno zdanie
                pod spodem — wcześniejsza ramka „Jak powstaje ten skrót" zajmowała
                pół ekranu i odsuwała pierwszą sesję poniżej zgięcia. */}
            <header>
                <h1 className="text-3xl font-extrabold tracking-tight text-white lg:text-4xl">
                    Sesje Rady Gminy
                </h1>
                <p className="mt-2 flex items-center gap-1.5 text-sm text-neutral-400">
                    <Landmark size={14} aria-hidden className="text-sky-400" />
                    Podsumowanie obrad — najważniejsze sprawy z każdej sesji
                </p>
                <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-neutral-400">
                    Przy każdym temacie stoi minuta nagrania — jak rozdziały na YouTube.
                    Klikasz znacznik i nagranie otwiera się dokładnie w tym miejscu.
                </p>
            </header>

            {loading && <p className="mt-8 text-sm text-neutral-500">Sprawdzam rejestr obrad…</p>}

            {failed && (
                <p className="mt-8 rounded-2xl border border-white/10 bg-[#0d1117] p-5 text-sm text-neutral-400">
                    Nie udało się pobrać skrótów obrad. Spróbuj odświeżyć stronę.
                </p>
            )}

            {!loading && !failed && sessions?.length === 0 && (
                <p className="mt-8 rounded-2xl border border-white/10 bg-[#0d1117] p-5 text-sm text-neutral-400">
                    Nie ma tu jeszcze żadnego skrótu. Pierwszy pojawi się po najbliższej sesji
                    Rady Gminy — terminy posiedzeń zbieramy w kalendarzu wydarzeń.
                </p>
            )}

            <div className="mt-6 space-y-4">
                {sessions?.map(session => {
                    const expanded = open === session.id;
                    const detail = details[session.id];
                    const summary = detail?.summary;

                    return (
                        <article
                            key={session.id}
                            className="overflow-hidden rounded-2xl border border-white/10 bg-[#0d1117]"
                        >
                            <div className="p-5">
                                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                                    {session.session_number && (
                                        <span className="text-sky-300">{session.session_number} sesja</span>
                                    )}
                                    <span aria-hidden>·</span>
                                    <span>{dateLabel(session.session_date)}</span>
                                    {session.duration_min && (
                                        <>
                                            <span aria-hidden>·</span>
                                            <span>{session.duration_min} min nagrania</span>
                                        </>
                                    )}
                                </div>

                                <h3 className="mt-2 text-xl font-black leading-tight tracking-tight text-white">
                                    {session.headline || session.title}
                                </h3>

                                {session.lead && (
                                    <p className="mt-2.5 text-[14.5px] leading-relaxed text-neutral-300">
                                        {session.lead}
                                    </p>
                                )}

                                <div className="mt-4 flex flex-wrap items-center gap-3">
                                    <button
                                        type="button"
                                        onClick={() => toggle(session.id)}
                                        aria-expanded={expanded}
                                        className="inline-flex items-center gap-1.5 rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-400"
                                    >
                                        {expanded ? 'Zwiń skrót' : 'Zobacz, co ustalono'}
                                        <ChevronDown
                                            size={15}
                                            aria-hidden
                                            className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
                                        />
                                    </button>

                                    {session.video_url && (
                                        <a
                                            href={session.video_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex items-center gap-1 text-[13px] font-semibold text-neutral-400 hover:text-neutral-200"
                                        >
                                            Całe nagranie obrad
                                            <ExternalLink size={12} aria-hidden />
                                        </a>
                                    )}
                                </div>
                            </div>

                            {expanded && (
                                <div className="border-t border-white/10 bg-black/20 px-5 pb-5 pt-5">
                                    {!detail && pending === session.id && (
                                        <p className="text-sm text-neutral-500">Wczytuję skrót…</p>
                                    )}

                                    {summary?.points?.length ? (
                                        <ul>
                                            {summary.points.map((point, i) => (
                                                <Point key={`${point.timestamp}-${i}`} point={point} />
                                            ))}
                                        </ul>
                                    ) : null}

                                    {summary?.resolutions?.length ? (
                                        <section className="mt-6 rounded-xl border border-white/10 bg-[#0d1117] p-4">
                                            <h4 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-neutral-500">
                                                <Gavel size={13} aria-hidden />
                                                Uchwały poddane pod głosowanie
                                            </h4>
                                            <ul className="mt-3">
                                                {summary.resolutions.map((resolution, i) => (
                                                    <Resolution key={`${resolution.subject}-${i}`} resolution={resolution} />
                                                ))}
                                            </ul>
                                        </section>
                                    ) : null}

                                    {detail && (
                                        <p className="mt-5 text-xs leading-relaxed text-neutral-500">
                                            Skrót powstał z zapisu całego nagrania obrad.
                                            {' '}
                                            <a
                                                href={session.page_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-neutral-400 underline decoration-white/20 underline-offset-2 hover:text-neutral-200"
                                            >
                                                Nagranie w galerii Gminy Rybno
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
