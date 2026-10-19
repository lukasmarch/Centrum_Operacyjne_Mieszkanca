/**
 * Redakcja sołectw (tylko admin): moderacja ogłoszeń, zaproszenia dla sołtysów,
 * lista nadanych ról.
 *
 * Moderacja pokazuje oryginał obok przedruku — odczyt robi model, a publikacja
 * idzie jako „sprawdzone przez redakcję" (AI Act art. 50), więc człowiek musi
 * mieć przed oczami jedno i drugie. Wykryte dane osobowe stoją nad tekstem,
 * nie pod nim.
 *
 * Opublikowane (E7): korekta i odwołanie zawsze z powodem — powód widzi
 * wyłącznie sołtys (mail, jego panel) i redakcja (historia); mieszkańcy
 * nie widzą procesu decyzyjnego wcale. Prośby sołtysa stoją
 * nad formularzem; ogłoszenie z otwartą prośbą wraca do kolejki „Do decyzji”.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Ban, Check, Copy, History, Loader2, PencilLine, RefreshCw, X } from 'lucide-react';
import { Chip, Notice, Skeleton, Tag, TagTone } from './simple/tv';
import {
    AdminInvitation, AdminPost, AdminRole, Correction, PostVersion, RoleDefinition, STATUS_LABELS,
    approvePost, correctPost, createInvitation, dismissRequest, editPost, fetchAdminPosts, fetchAdminRoles,
    fetchInvitations, fetchPostImage, fetchPostVersions, fetchRoleDefinitions, parseUtc, rejectPost,
    rereadPost, revokeInvitation, revokeRole, withdrawPost,
} from '../src/services/solectwaApi';

type Section = 'posts' | 'invitations' | 'roles';

// Panel redakcji w języku „Paska informacyjnego”: płaski panel z chabrową
// krawędzią, pola z obrysem 2 px, przyciski 44 px, kąty proste
const card = 'border-t-2 border-tv-blue bg-tv-panel p-5 sm:p-6';
const input = 'min-h-[44px] w-full border-2 border-tv-seam bg-tv-ink px-3 py-2 text-[16px] text-white outline-none transition-colors placeholder:text-tv-muted focus:border-tv-paper disabled:opacity-60';
const fieldLabel = 'font-cond mb-1 block text-[13px] font-extrabold uppercase tracking-wide text-tv-muted';
const btnPrimary = 'font-cond inline-flex min-h-[44px] items-center justify-center gap-2 bg-tv-blue px-4 text-[16px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-not-allowed disabled:opacity-40';
const btnLine = 'inline-flex min-h-[44px] items-center justify-center gap-2 border-2 border-tv-seam px-4 text-[15px] font-semibold text-tv-paper transition-colors hover:border-tv-paper hover:text-white disabled:cursor-not-allowed disabled:opacity-40';
const errorText = 'text-[15px] font-semibold text-tv-yellow';

// Kolor stanu liczony tu, nie z `STATUS_LABELS.tone` (klasy starego świata)
const POST_TONE: Partial<Record<AdminPost['status'], TagTone>> = {
    processing: 'seam',
    pending: 'yellow',
    failed: 'yellow',
    published: 'blue',
    rejected: 'seam',
};

const dateLabel = (value: string | null) => {
    const d = parseUtc(value);
    return d ? d.toLocaleString('pl-PL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';
};

const INVITATION_STATE: Record<AdminInvitation['state'], string> = {
    active: 'aktywne',
    used: 'przyjęte',
    revoked: 'wycofane',
    expired: 'wygasło',
};

// ── Moderacja ────────────────────────────────────────────────────────────

const PostImages: React.FC<{ post: AdminPost }> = ({ post }) => {
    const [urls, setUrls] = useState<string[]>([]);
    useEffect(() => {
        let alive = true;
        const created: string[] = [];
        (async () => {
            for (let i = 0; i < post.image_count; i++) {
                try {
                    const url = await fetchPostImage(post.id, i);
                    created.push(url);
                    if (alive) setUrls([...created]);
                } catch {
                    // brak pliku — pokażemy tyle, ile się da
                }
            }
        })();
        return () => {
            alive = false;
            created.forEach((u) => URL.revokeObjectURL(u));
        };
    }, [post.id, post.image_count]);

    if (!post.image_count) {
        return <p className="text-[14px] text-tv-muted">Zdjęcia oryginału skasowane (retencja).</p>;
    }
    return (
        <div className="space-y-px bg-tv-seam">
            {urls.map((url, i) => (
                <a key={url} href={url} target="_blank" rel="noreferrer" className="block">
                    <img src={url} alt={`Strona ${i + 1}`} className="w-full" />
                </a>
            ))}
            {urls.length < post.image_count && <Skeleton className="h-40" />}
        </div>
    );
};

// ── Po publikacji: korekta, odwołanie, historia (E7) ─────────────────────

const pad = (n: number) => String(n).padStart(2, '0');
const localDay = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const localTime = (d: Date) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;

const VERSION_KIND: Record<PostVersion['kind'], string> = {
    publication: 'Publikacja',
    correction: 'Korekta',
    withdrawal: 'Odwołanie',
};

const VersionHistory: React.FC<{ postId: number }> = ({ postId }) => {
    const [versions, setVersions] = useState<PostVersion[] | null>(null);
    const [error, setError] = useState('');
    useEffect(() => {
        fetchPostVersions(postId).then(setVersions).catch((e) => setError(e.message));
    }, [postId]);
    if (error) return <p className={errorText}>{error}</p>;
    if (!versions) return <Loader2 className="h-4 w-4 animate-spin text-tv-muted" aria-label="Wczytuję historię" />;
    return (
        <ol className="space-y-3">
            {versions.map((v) => (
                <li key={v.version} className="border-l-2 border-tv-seam bg-tv-panel2 p-3 text-[15px] text-tv-paper">
                    <p className="tabular text-[13px] text-tv-muted">
                        v{v.version} · {VERSION_KIND[v.kind]} · {dateLabel(v.created_at)} · {v.changed_by ?? '—'}
                    </p>
                    {v.reason && <p className="mt-1 font-semibold text-tv-yellow">Powód: {v.reason}</p>}
                    <p className="mt-1 font-semibold text-white">{v.title}</p>
                    <p className="text-tv-muted">termin: {v.event_at ? dateLabel(v.event_at) : 'brak'}</p>
                    {v.summary && <p className="mt-1 text-[#d7dbe8]">{v.summary}</p>}
                </li>
            ))}
        </ol>
    );
};

interface Draft { title: string; summary: string; transcript: string }

const PublishedActions: React.FC<{ post: AdminPost; draft: Draft; onChanged: () => void }> = ({ post, draft, onChanged }) => {
    const { title, summary, transcript } = draft;
    const start = parseUtc(post.event_at);
    const end = parseUtc(post.event_until);
    const allDay = !!start && !end && start.getHours() === 0 && start.getMinutes() === 0;
    const correctionRequest = post.open_requests.find((r) => r.kind === 'correction');
    const withdrawalRequest = post.open_requests.find((r) => r.kind === 'withdrawal');

    const [mode, setMode] = useState<'none' | 'correct' | 'withdraw' | 'history'>('none');
    const [termAction, setTermAction] = useState<Correction['term_action']>('keep');
    const [day, setDay] = useState(start ? localDay(start) : '');
    const [from, setFrom] = useState(start && !allDay ? localTime(start) : '');
    const [to, setTo] = useState(end ? localTime(end) : '');
    const [reason, setReason] = useState('');
    const [dismissReason, setDismissReason] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    const run = async (action: () => Promise<unknown>) => {
        if (mode !== 'none' && mode !== 'history' && reason.trim().length < 3) {
            setError('Podaj powód — zobaczą go mieszkańcy i sołtys.');
            return;
        }
        setBusy(true);
        setError('');
        try {
            await action();
            onChanged();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Nie udało się');
        } finally {
            setBusy(false);
        }
    };

    const submitCorrection = () => run(() => {
        if (termAction === 'set' && !day) throw new Error('Wybierz dzień nowego terminu');
        if (to && !from) throw new Error('Godzina końca wymaga godziny rozpoczęcia');
        const data: Correction = { reason, term_action: termAction, request_id: correctionRequest?.id };
        if (title !== (post.title ?? '')) data.title = title;
        if (summary !== (post.summary ?? '')) data.summary = summary;
        if (transcript !== (post.transcript ?? '')) data.transcript = transcript;
        if (termAction === 'set') data.term = { day, start: from || null, end: to || null };
        return correctPost(post.id, data);
    });
    const submitWithdraw = () => run(() => withdrawPost(post.id, reason, withdrawalRequest?.id));

    const tab = (m: typeof mode, label: string, Icon: typeof PencilLine, tone = '') => (
        <button onClick={() => { setMode(mode === m ? 'none' : m); setError(''); }}
            aria-pressed={mode === m}
            className={`${btnLine} ${mode === m ? '!border-tv-paper bg-tv-panel2 !text-white' : ''} ${tone}`}>
            <Icon className="h-4 w-4" aria-hidden /> {label}
        </button>
    );

    return (
        <div className="mt-5 space-y-3">
            {post.open_requests.map((r) => (
                <div key={r.id} className="border-l-4 border-tv-yellow bg-tv-panel2 p-3 text-[15px]">
                    <p className="font-semibold text-tv-yellow">
                        Sołtys prosi o {r.kind === 'correction' ? 'korektę' : 'ODWOŁANIE'} · {dateLabel(r.created_at)}
                    </p>
                    <p className="mt-1 text-white">„{r.message}”</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                        <input className={`${input} sm:max-w-xs`} placeholder="Odpowiedź dla sołtysa (opcjonalnie)"
                            value={dismissReason} onChange={(e) => setDismissReason(e.target.value)} />
                        <button onClick={() => run(() => dismissRequest(r.id, dismissReason))} disabled={busy}
                            className={btnLine}>
                            Zostaw bez zmian
                        </button>
                    </div>
                </div>
            ))}

            {post.corrected_at && (
                <p className="tabular text-[13px] text-tv-muted">Ostatnia korekta: {dateLabel(post.corrected_at)} · wersja {post.version}</p>
            )}

            <div className="flex flex-wrap gap-2">
                {tab('correct', 'Popraw', PencilLine)}
                {tab('withdraw', 'Odwołaj', Ban)}
                {tab('history', 'Historia', History)}
            </div>

            {mode === 'correct' && (
                <div className="space-y-3 border-2 border-tv-seam p-4">
                    <p className="text-[15px] text-tv-muted">
                        Tytuł, podsumowanie i przedruk poprawiasz w polach powyżej
                        {(title !== (post.title ?? '') || summary !== (post.summary ?? '') || transcript !== (post.transcript ?? ''))
                            ? ' — są zmiany w tekście.' : '.'}
                    </p>
                    <div>
                        <label className={fieldLabel}>Termin</label>
                        <div className="mt-1 flex flex-wrap gap-4 text-[15px] text-tv-paper">
                            {([['keep', 'bez zmian'], ['set', 'nowy termin'], ['clear', 'usuń termin']] as const).map(([value, label]) => (
                                <label key={value} className="inline-flex min-h-[44px] items-center gap-2">
                                    <input type="radio" checked={termAction === value} onChange={() => setTermAction(value)} /> {label}
                                </label>
                            ))}
                        </div>
                        {termAction === 'set' && (
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-[15px]">
                                <input type="date" className={`${input} max-w-[11rem]`} value={day} onChange={(e) => setDay(e.target.value)} />
                                <input type="time" className={`${input} max-w-[8rem]`} value={from} onChange={(e) => setFrom(e.target.value)} />
                                <span className="text-tv-muted">–</span>
                                <input type="time" className={`${input} max-w-[8rem]`} value={to} onChange={(e) => setTo(e.target.value)} />
                                <span className="text-[13px] text-tv-muted">bez godziny = cały dzień</span>
                            </div>
                        )}
                        {termAction === 'set' && transcript === (post.transcript ?? '') && (
                            <p className="mt-2 bg-tv-yellow px-3 py-2 text-[14px] font-semibold text-tv-ink">
                                Przedruk powyżej może wciąż zawierać starą datę lub godzinę — mieszkaniec zobaczyłby dwa różne
                                terminy. Popraw je w przedruku po cichu, bez adnotacji o korekcie (proces zostaje między redakcją a sołtysem).
                            </p>
                        )}
                        {termAction === 'clear' && (
                            <p className="mt-1 text-[13px] text-tv-muted">Wydarzenie zniknie z kalendarza.</p>
                        )}
                        <p className="mt-1 text-[13px] text-tv-muted">
                            Teraz: {start ? (allDay ? `${start.toLocaleDateString('pl-PL')} (cały dzień)` : dateLabel(post.event_at)) : 'brak'}.
                            Zaktualizowany termin wróci do najbliższego briefingu — bez wzmianki o zmianie.
                        </p>
                    </div>
                    <input className={input} placeholder="Powód korekty (zobaczy go tylko sołtys)"
                        value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
                    <button onClick={submitCorrection} disabled={busy}
                        className={btnPrimary}>
                        <Check className="h-4 w-4" aria-hidden /> Opublikuj korektę
                    </button>
                </div>
            )}

            {mode === 'withdraw' && (
                <div className="space-y-3 border-2 border-tv-red p-4">
                    <p className="text-[15px] text-tv-paper">
                        Ogłoszenie zniknie z wiadomości, kalendarza, briefingu i odpowiedzi asystenta.
                        Pod jego adresem mieszkaniec zobaczy tylko „nieaktualne” — bez powodu.
                    </p>
                    <input className={input} placeholder="Powód odwołania (zobaczy go tylko sołtys)"
                        value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
                    <button onClick={submitWithdraw} disabled={busy}
                        className="font-cond inline-flex min-h-[44px] items-center justify-center gap-2 bg-tv-red px-4 text-[16px] font-extrabold uppercase tracking-wide text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40">
                        <Ban className="h-4 w-4" aria-hidden /> Odwołaj ogłoszenie
                    </button>
                </div>
            )}

            {mode === 'history' && <VersionHistory postId={post.id} />}

            {error && <p className={errorText} role="alert">{error}</p>}
        </div>
    );
};

const PostModeration: React.FC<{ post: AdminPost; onChanged: () => void }> = ({ post, onChanged }) => {
    const [title, setTitle] = useState(post.title ?? '');
    const [summary, setSummary] = useState(post.summary ?? '');
    const [transcript, setTranscript] = useState(post.transcript ?? '');
    const [reason, setReason] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const dirty = title !== (post.title ?? '') || summary !== (post.summary ?? '') || transcript !== (post.transcript ?? '');
    const decided = post.status === 'published' || post.status === 'rejected' || post.status === 'withdrawn';
    // Opublikowane poprawia się w tych samych polach — wysyła je „Opublikuj korektę”
    const locked = post.status === 'rejected' || post.status === 'withdrawn';

    const run = async (action: () => Promise<unknown>) => {
        setBusy(true);
        setError('');
        try {
            await action();
            onChanged();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Nie udało się');
        } finally {
            setBusy(false);
        }
    };

    const save = () => editPost(post.id, { title, summary, transcript });
    const approve = () => run(async () => {
        if (dirty) await save();
        await approvePost(post.id);
    });

    const status = STATUS_LABELS[post.status];
    const eventAt = parseUtc(post.event_at);

    return (
        <div className={card}>
            <div className="mb-3 flex flex-wrap items-center gap-2">
                <Tag tone={POST_TONE[post.status] ?? 'seam'}>{status.label}</Tag>
                <span className="text-[15px] font-semibold text-white">{post.signed_as}</span>
                <span className="tabular text-[13px] text-tv-muted">
                    {dateLabel(post.created_at)} · {post.author_name} ({post.author_email})
                </span>
            </div>

            {post.status === 'withdrawn' && (
                <p className="mb-3 text-sm text-red-300">Odwołane {dateLabel(post.withdrawn_at)}: {post.withdraw_reason}</p>
            )}
            {post.ai_error && (
                <p className="mb-3 flex gap-2 bg-tv-yellow px-4 py-3 text-[15px] text-tv-ink"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{post.ai_error}</p>
            )}
            {!!post.personal_data?.length && (
                <div className="mb-3 bg-tv-yellow px-4 py-3 text-[15px] text-tv-ink">
                    <p className="mb-1 font-bold">Dane osobowe w piśmie — sprawdź przedruk:</p>
                    <ul className="list-disc pl-5 space-y-0.5">
                        {post.personal_data.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                </div>
            )}
            {!!post.illegible?.length && (
                <p className="mb-3 text-[15px] text-[#d7dbe8]">Nieczytelne: {post.illegible.join('; ')}</p>
            )}
            {post.note && <p className="mb-3 text-[15px] text-[#d7dbe8]">Dopisek sołtysa: „{post.note}”</p>}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <div>
                    <p className={fieldLabel}>Oryginał (tylko redakcja)</p>
                    <PostImages post={post} />
                </div>
                <div className="space-y-3">
                    <div>
                        <label className={fieldLabel}>Tytuł</label>
                        <input className={input} value={title} onChange={(e) => setTitle(e.target.value)} disabled={locked} />
                    </div>
                    <div>
                        <label className={fieldLabel}>Podsumowanie</label>
                        <textarea className={input} rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} disabled={locked} />
                    </div>
                    <div>
                        <label className={fieldLabel}>Przedruk</label>
                        <textarea className={`${input} text-[14px] leading-relaxed`} rows={14} value={transcript} onChange={(e) => setTranscript(e.target.value)} disabled={locked} />
                    </div>
                    <p className="tabular text-[13px] text-tv-muted">
                        {post.doc_type ? `${post.doc_type} · ` : ''}
                        termin: {eventAt ? eventAt.toLocaleString('pl-PL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }) : 'brak'}
                    </p>
                </div>
            </div>

            {error && <p role="alert" className={`mt-3 ${errorText}`}>{error}</p>}

            {!decided && (
                <div className="mt-5 flex flex-wrap items-center gap-2">
                    <button onClick={approve} disabled={busy || post.status === 'processing'}
                        className={btnPrimary}>
                        <Check className="h-4 w-4" aria-hidden /> Publikuj{dirty ? ' z poprawkami' : ''}
                    </button>
                    {dirty && (
                        <button onClick={() => run(save)} disabled={busy}
                            className={btnLine}>Zapisz poprawki</button>
                    )}
                    <button onClick={() => run(() => rereadPost(post.id))} disabled={busy || !post.image_count}
                        className={btnLine}>
                        <RefreshCw className="h-4 w-4" aria-hidden /> Odczytaj ponownie
                    </button>
                    <input className={`${input} sm:max-w-xs`} placeholder="Powód odrzucenia (trafi do sołtysa)"
                        value={reason} onChange={(e) => setReason(e.target.value)} />
                    <button onClick={() => run(() => rejectPost(post.id, reason))} disabled={busy}
                        className={btnLine}>
                        <X className="h-4 w-4" aria-hidden /> Odrzuć
                    </button>
                </div>
            )}
            {post.status === 'published' && <PublishedActions post={post} draft={{ title, summary, transcript }} onChanged={onChanged} />}
            {post.status === 'withdrawn' && (
                <details className="mt-4">
                    <summary className="min-h-[44px] cursor-pointer text-[15px] font-semibold text-tv-muted hover:text-white">Historia</summary>
                    <div className="mt-2"><VersionHistory postId={post.id} /></div>
                </details>
            )}
            {post.url && (
                <a href={post.url} className="mt-3 inline-flex min-h-[44px] items-center text-[15px] font-bold text-tv-bluesoft underline-offset-4 hover:text-white hover:underline">Zobacz na stronie →</a>
            )}
        </div>
    );
};

const PostsSection: React.FC = () => {
    const [filter, setFilter] = useState<'queue' | 'all'>('queue');
    const [posts, setPosts] = useState<AdminPost[] | null>(null);
    const [error, setError] = useState('');

    const load = useCallback(() => {
        fetchAdminPosts()
            .then((all) => setPosts(filter === 'queue'
                ? all.filter((p) => ['processing', 'pending', 'failed'].includes(p.status) || p.open_requests.length > 0)
                : all))
            .catch((e) => setError(e.message));
    }, [filter]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => {
        if (!posts?.some((p) => p.status === 'processing')) return;
        const t = window.setTimeout(load, 4000);
        return () => window.clearTimeout(t);
    }, [posts, load]);

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap gap-1.5">
                {(['queue', 'all'] as const).map((f) => (
                    <Chip key={f} active={filter === f} onClick={() => setFilter(f)}>
                        {f === 'queue' ? 'Do decyzji' : 'Wszystkie'}
                    </Chip>
                ))}
            </div>
            {error && <Notice tone="warn" role="alert">{error}</Notice>}
            {posts === null ? <Skeleton className="h-40" /> :
                posts.length === 0 ? <Notice>Nic nie czeka na decyzję.</Notice> :
                    posts.map((p) => <PostModeration key={`${p.id}-${p.status}-${p.version}-${p.open_requests.length}`} post={p} onChanged={load} />)}
        </div>
    );
};

// ── Zaproszenia ──────────────────────────────────────────────────────────

const InvitationsSection: React.FC = () => {
    const [definitions, setDefinitions] = useState<RoleDefinition[]>([]);
    const [invitations, setInvitations] = useState<AdminInvitation[]>([]);
    const [scope, setScope] = useState('');
    const [label, setLabel] = useState('');
    const [created, setCreated] = useState<AdminInvitation | null>(null);
    const [copied, setCopied] = useState<number | null>(null);
    const [error, setError] = useState('');

    const load = useCallback(() => {
        fetchInvitations().then(setInvitations).catch((e) => setError(e.message));
    }, []);
    useEffect(() => {
        fetchRoleDefinitions().then(setDefinitions).catch((e) => setError(e.message));
        load();
    }, [load]);

    const soltys = definitions.find((d) => d.role === 'soltys');

    const create = async () => {
        setError('');
        try {
            const inv = await createInvitation('soltys', scope, label);
            setCreated(inv);
            setLabel('');
            load();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Nie udało się');
        }
    };

    const copy = (inv: AdminInvitation) => {
        navigator.clipboard.writeText(inv.url).then(() => {
            setCopied(inv.id);
            window.setTimeout(() => setCopied(null), 2000);
        });
    };

    return (
        <div className="space-y-4">
            <div className={card}>
                <h3 className="font-cond mb-1 text-[20px] font-extrabold text-white">Nowe zaproszenie dla sołtysa</h3>
                <p className="mb-4 max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">
                    Po rozmowie telefonicznej wygeneruj link i wyślij go SMS-em. Kto go otworzy i założy konto
                    (albo się zaloguje), od razu zostaje sołtysem wybranego sołectwa. Link działa 14 dni, jeden raz.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <select className={input} value={scope} onChange={(e) => setScope(e.target.value)}>
                        <option value="">Sołectwo…</option>
                        {soltys?.scopes.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <input className={input} placeholder="Dla kogo (tylko dla Ciebie)" value={label}
                        onChange={(e) => setLabel(e.target.value)} maxLength={100} />
                    <button onClick={create} disabled={!scope}
                        className={btnPrimary}>
                        Generuj link
                    </button>
                </div>
                {created && (
                    <div className="mt-4 border border-tv-seam bg-tv-ink p-3 text-[15px]">
                        <p className="mb-1 flex items-center gap-2 font-semibold text-white"><Check className="h-4 w-4 shrink-0 text-tv-green" aria-hidden />{created.signed_as} — link gotowy</p>
                        <div className="flex items-center gap-2">
                            <span className="min-w-0 flex-1 truncate text-[14px] text-tv-bluesoft">{created.url}</span>
                            <button onClick={() => copy(created)} className={btnLine}>
                                <Copy className="h-4 w-4" aria-hidden /> {copied === created.id ? 'Skopiowano' : 'Kopiuj'}
                            </button>
                        </div>
                    </div>
                )}
                {error && <p role="alert" className={`mt-3 ${errorText}`}>{error}</p>}
            </div>

            <div className={card}>
                <h3 className="font-cond mb-3 text-[20px] font-extrabold text-white">Wystawione zaproszenia</h3>
                {invitations.length === 0 ? <p className="text-[15px] text-tv-muted">Brak zaproszeń.</p> : (
                    <ul className="divide-y divide-tv-seam text-[15px]">
                        {invitations.map((inv) => (
                            <li key={inv.id} className="py-3 flex flex-wrap items-center gap-2">
                                <span className="font-semibold text-white">{inv.signed_as}</span>
                                {inv.invitee_label && <span className="text-[#d7dbe8]">· {inv.invitee_label}</span>}
                                <span className="tabular text-[13px] text-tv-muted">
                                    · {INVITATION_STATE[inv.state]}
                                    {inv.state === 'used' && inv.used_by_email ? ` przez ${inv.used_by_email}` : ''}
                                    {inv.state === 'active' ? ` do ${dateLabel(inv.expires_at)}` : ''}
                                </span>
                                {inv.state === 'active' && (
                                    <span className="ml-auto flex gap-2">
                                        <button onClick={() => copy(inv)} className={btnLine}>
                                            <Copy className="h-4 w-4" aria-hidden /> {copied === inv.id ? 'Skopiowano' : 'Kopiuj link'}
                                        </button>
                                        <button onClick={() => revokeInvitation(inv.id).then(load).catch((e) => setError(e.message))}
                                            className={btnLine}>Wycofaj</button>
                                    </span>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
};

// ── Role ─────────────────────────────────────────────────────────────────

const RolesSection: React.FC = () => {
    const [roles, setRoles] = useState<AdminRole[] | null>(null);
    const [error, setError] = useState('');
    const load = useCallback(() => {
        fetchAdminRoles().then(setRoles).catch((e) => setError(e.message));
    }, []);
    useEffect(() => { load(); }, [load]);

    const revoke = async (role: AdminRole) => {
        if (!window.confirm(`Odebrać rolę „${role.signed_as}” kontu ${role.user_email}? Konto straci Premium z tytułu roli.`)) return;
        try {
            await revokeRole(role.id);
            load();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Nie udało się');
        }
    };

    return (
        <div className={card}>
            <h3 className="font-cond mb-3 text-[20px] font-extrabold text-white">Sołtysi z kontem</h3>
            {error && <p role="alert" className={`mb-2 ${errorText}`}>{error}</p>}
            {roles === null ? <Skeleton className="h-20" /> :
                roles.length === 0 ? <p className="text-[15px] text-tv-muted">Nikt jeszcze nie przyjął zaproszenia.</p> : (
                    <ul className="divide-y divide-tv-seam text-[15px]">
                        {roles.map((r) => (
                            <li key={r.id} className="py-3 flex flex-wrap items-center gap-2">
                                <span className="font-semibold text-white">{r.signed_as}</span>
                                <span className="text-[#d7dbe8]">· {r.user_name} ({r.user_email})</span>
                                <span className="tabular text-[13px] text-tv-muted">· od {dateLabel(r.verified_at)}</span>
                                <button onClick={() => revoke(r)} className={`${btnLine} ml-auto`}>
                                    Odbierz rolę
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
        </div>
    );
};

const SolectwaAdminPanel: React.FC = () => {
    const [section, setSection] = useState<Section>('posts');
    const tabs: { id: Section; label: string }[] = [
        { id: 'posts', label: 'Ogłoszenia' },
        { id: 'invitations', label: 'Zaproszenia' },
        { id: 'roles', label: 'Sołtysi' },
    ];
    return (
        <div className="space-y-5">
            <div role="group" aria-label="Redakcja sołectw" className="flex flex-wrap gap-1.5">
                {tabs.map((t) => (
                    <Chip key={t.id} active={section === t.id} onClick={() => setSection(t.id)}>
                        {t.label}
                    </Chip>
                ))}
            </div>
            {section === 'posts' && <PostsSection />}
            {section === 'invitations' && <InvitationsSection />}
            {section === 'roles' && <RolesSection />}
        </div>
    );
};

export default SolectwaAdminPanel;
