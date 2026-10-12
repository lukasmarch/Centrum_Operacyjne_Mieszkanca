/**
 * Ogłoszenie sołectwa — `/ogloszenie?id=…`. Tu prowadzi link z feedu i ten,
 * który sołtys wkleja na swoim profilu FB.
 *
 * Trzy warstwy: tytuł i podsumowanie (oznaczone jako przygotowane automatycznie
 * i sprawdzone przez redakcję — AI Act art. 50), pełny przedruk pisma, podpis
 * funkcją. Zdjęcia oryginału tu nie ma i nie będzie: widzi je tylko redakcja.
 */
import React, { useEffect, useState } from 'react';
import { CalendarDays, ChevronDown, FileText, Sparkles } from 'lucide-react';
import { Notice, Skeleton, Tag } from '../../components/simple/tv';
import { PublicPost, fetchPublicPost, parseUtc } from '../services/solectwaApi';

const idFromUrl = () => Number(new URLSearchParams(window.location.search).get('id')) || 0;

const termLabel = (post: PublicPost): string | null => {
    const start = parseUtc(post.event_at);
    if (!start) return null;
    const end = parseUtc(post.event_until);
    const day = start.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    // Ta sama reguła co `utils/eventTime.isAllDay`: bez końca i o lokalnej północy
    if (!end && start.getHours() === 0 && start.getMinutes() === 0) return day;
    const hour = (d: Date) => d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
    return `${day}, ${hour(start)}${end ? `–${hour(end)}` : ''}`;
};

const SolectwoPostPage: React.FC = () => {
    const [post, setPost] = useState<PublicPost | null>(null);
    const [error, setError] = useState('');
    const [showTranscript, setShowTranscript] = useState(true);

    useEffect(() => {
        const id = idFromUrl();
        if (!id) {
            setError('Nie znaleziono ogłoszenia.');
            return;
        }
        fetchPublicPost(id)
            .then((p) => {
                setPost(p);
                document.title = `${p.title} — ${p.signed_as} | RybnoLive`;
            })
            .catch(() => setError('Nie znaleziono ogłoszenia.'));
    }, []);

    if (error) {
        return <div className="max-w-2xl"><Notice>{error}</Notice></div>;
    }
    if (!post) {
        return (
            <div aria-label="Wczytuję ogłoszenie…" className="max-w-2xl space-y-px">
                <Skeleton className="h-7 w-48" />
                <Skeleton className="h-28" />
                <Skeleton className="h-40" />
            </div>
        );
    }

    const term = termLabel(post);
    const published = parseUtc(post.published_at);

    return (
        <article className="flex max-w-2xl flex-col">
            {/* Plakietka z nazwą sołectwa nad pasem tytułu — ten sam układ co kafle pulpitu */}
            <Tag>Sołectwo {post.solectwo}</Tag>
            <header className="border-t-2 border-tv-blue bg-tv-panel px-4 pb-4 pt-3 lg:px-5">
                <h1 className="font-cond text-[26px] font-extrabold leading-tight text-white lg:text-[34px]">{post.title}</h1>
                <p className="mt-1.5 text-[15px] leading-snug text-tv-muted">
                    <span className="font-bold text-tv-paper">{post.signed_as}</span>
                    {published && <span className="tabular">{` · ${published.toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })}`}</span>}
                </p>
            </header>

            {/* Termin to zapowiedź — żółty pasek kontekstu pod pasem tytułu */}
            {term && (
                <div className="flex min-h-[48px] items-center gap-3 bg-tv-yellow px-4 py-2 text-tv-ink lg:px-5">
                    <CalendarDays size={18} className="shrink-0" aria-hidden />
                    <span className="tabular text-[16px] font-bold first-letter:uppercase">{term}</span>
                </div>
            )}

            {post.summary && (
                <section className="mt-px bg-tv-panel px-4 py-4 lg:px-5">
                    <p className="max-w-[70ch] text-[16px] leading-relaxed text-white">{post.summary}</p>
                    <p className="mt-3 flex items-center gap-1.5 text-[13px] text-tv-muted">
                        <Sparkles size={14} aria-hidden />
                        Podsumowanie przygotowane automatycznie, sprawdzone przez redakcję.
                    </p>
                </section>
            )}

            {post.transcript && (
                <section className="mt-6 flex flex-col">
                    <button
                        onClick={() => setShowTranscript((v) => !v)}
                        aria-expanded={showTranscript}
                        className="flex min-h-[52px] w-full items-center gap-2 border-t-2 border-tv-seam bg-tv-panel px-4 text-left text-[16px] font-bold text-white transition-colors hover:bg-tv-panel2 lg:px-5"
                    >
                        <FileText size={16} className="text-tv-muted" aria-hidden />
                        Pełna treść pisma
                        <span className="ml-auto inline-flex items-center gap-1 text-[14px] font-bold text-tv-bluesoft">
                            {showTranscript ? 'zwiń' : 'rozwiń'}
                            <ChevronDown size={16} aria-hidden className={`transition-transform ${showTranscript ? 'rotate-180' : ''}`} />
                        </span>
                    </button>
                    {showTranscript && (
                        <div className="bg-tv-panel px-4 pb-5 lg:px-5">
                            <p className="max-w-[70ch] whitespace-pre-line text-[15px] leading-relaxed text-[#d7dbe8]">{post.transcript}</p>
                            <p className="mt-4 max-w-[70ch] border-t border-tv-seam pt-3 text-[13px] leading-relaxed text-tv-muted">
                                Tekst odczytany automatycznie ze zdjęcia pisma. W razie rozbieżności rozstrzyga oryginał.
                                Dane osób prywatnych zastąpiliśmy znacznikiem [dane osobowe].
                            </p>
                        </div>
                    )}
                </section>
            )}
        </article>
    );
};

export default SolectwoPostPage;
