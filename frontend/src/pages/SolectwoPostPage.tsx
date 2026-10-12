/**
 * Ogłoszenie sołectwa — `/ogloszenie?id=…`. Tu prowadzi link z feedu i ten,
 * który sołtys wkleja na swoim profilu FB.
 *
 * Trzy warstwy: tytuł i podsumowanie (oznaczone jako przygotowane automatycznie
 * i sprawdzone przez redakcję — AI Act art. 50), pełny przedruk pisma, podpis
 * funkcją. Zdjęcia oryginału tu nie ma i nie będzie: widzi je tylko redakcja.
 *
 * Po publikacji (E7): odwołane ogłoszenie zostaje pod tym samym adresem — link
 * krąży po Facebooku — ale pokazuje tylko tytuł i informację o odwołaniu.
 * Poprawione mówi, kiedy i dlaczego je poprawiono; starej treści nie pokazujemy.
 */
import React, { useEffect, useState } from 'react';
import { Ban, CalendarDays, FileText, History, Loader2, Sparkles } from 'lucide-react';
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

const shortDate = (value: string | null) => {
    const d = parseUtc(value);
    return d ? d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }) : '';
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
        return <div className="max-w-2xl mx-auto px-4 py-16 text-center text-neutral-400">{error}</div>;
    }
    if (!post) {
        return <div className="py-16 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-neutral-500" /></div>;
    }

    const term = termLabel(post);
    const published = parseUtc(post.published_at);
    const withdrawn = post.status === 'withdrawn';
    const corrections = post.changes.filter((c) => c.kind === 'correction');

    return (
        <article className="max-w-2xl mx-auto px-4 py-8 space-y-5">
            <header>
                <p className="text-xs font-bold uppercase tracking-wider text-emerald-400">Ogłoszenie sołectwa {post.solectwo}</p>
                <h1 className={`text-2xl sm:text-3xl font-black mt-2 leading-tight ${withdrawn ? 'text-neutral-400 line-through decoration-2' : ''}`}>{post.title}</h1>
                <p className="text-sm text-neutral-400 mt-2">
                    {post.signed_as}
                    {published && ` · ${published.toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })}`}
                </p>
            </header>

            {withdrawn && (
                <div className="flex items-start gap-3 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3">
                    <Ban className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                    <div>
                        <p className="font-semibold text-red-200">Ogłoszenie odwołane {shortDate(post.withdrawn_at)}</p>
                        {post.withdraw_reason && <p className="text-sm text-red-100/80 mt-0.5">{post.withdraw_reason}</p>}
                        <p className="text-xs text-neutral-400 mt-1">Treść i termin z odwołanego ogłoszenia nie obowiązują.</p>
                    </div>
                </div>
            )}

            {!withdrawn && corrections.length > 0 && (
                <div className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/5 px-4 py-3">
                    <History className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                    <div className="text-sm">
                        <p className="font-semibold text-amber-200">
                            Ogłoszenie poprawione{corrections.length > 1 ? ` (${corrections.length}×)` : ''}
                        </p>
                        <ul className="mt-0.5 space-y-0.5 text-amber-100/80">
                            {corrections.map((c) => (
                                <li key={c.at}>{shortDate(c.at)}{c.reason ? `: ${c.reason}` : ''}</li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}

            {term && (
                <div className="flex items-center gap-3 rounded-2xl border border-blue-500/30 bg-blue-500/5 px-4 py-3">
                    <CalendarDays className="w-5 h-5 text-blue-400 shrink-0" />
                    <span className="font-semibold first-letter:uppercase">{term}</span>
                </div>
            )}

            {post.summary && (
                <section className="rounded-2xl bg-gray-950 border border-gray-800/50 p-5">
                    <p className="text-base leading-relaxed text-neutral-100">{post.summary}</p>
                    <p className="mt-3 text-xs text-neutral-500 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5" />
                        Podsumowanie przygotowane automatycznie, sprawdzone przez redakcję.
                    </p>
                </section>
            )}

            {post.transcript && (
                <section className="rounded-2xl bg-gray-950 border border-gray-800/50">
                    <button onClick={() => setShowTranscript((v) => !v)}
                        className="w-full flex items-center gap-2 px-5 py-4 text-left font-semibold">
                        <FileText className="w-4 h-4 text-neutral-400" />
                        Pełna treść pisma
                        <span className="ml-auto text-xs text-neutral-500">{showTranscript ? 'zwiń' : 'rozwiń'}</span>
                    </button>
                    {showTranscript && (
                        <div className="px-5 pb-5">
                            <p className="whitespace-pre-line text-sm leading-relaxed text-neutral-200 font-serif">{post.transcript}</p>
                            <p className="mt-4 text-xs text-neutral-500">
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
