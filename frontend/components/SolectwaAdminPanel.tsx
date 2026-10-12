/**
 * Redakcja sołectw (tylko admin): moderacja ogłoszeń, zaproszenia dla sołtysów,
 * lista nadanych ról.
 *
 * Moderacja pokazuje oryginał obok przedruku — odczyt robi model, a publikacja
 * idzie jako „sprawdzone przez redakcję" (AI Act art. 50), więc człowiek musi
 * mieć przed oczami jedno i drugie. Wykryte dane osobowe stoją nad tekstem,
 * nie pod nim.
 *
 * Opublikowane (E7): korekta i odwołanie zawsze z powodem — powód widzą
 * mieszkańcy na stronie ogłoszenia i sołtys w mailu. Prośby sołtysa stoją
 * nad formularzem; ogłoszenie z otwartą prośbą wraca do kolejki „Do decyzji”.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Ban, Check, Copy, History, Loader2, PencilLine, RefreshCw, X } from 'lucide-react';
import {
    AdminInvitation, AdminPost, AdminRole, Correction, PostVersion, RoleDefinition, STATUS_LABELS,
    approvePost, correctPost, createInvitation, dismissRequest, editPost, fetchAdminPosts, fetchAdminRoles,
    fetchInvitations, fetchPostImage, fetchPostVersions, fetchRoleDefinitions, parseUtc, rejectPost,
    rereadPost, revokeInvitation, revokeRole, withdrawPost,
} from '../src/services/solectwaApi';

type Section = 'posts' | 'invitations' | 'roles';

const card = 'bg-gray-950 rounded-2xl p-6 border border-gray-800/50';
const input = 'w-full rounded-xl bg-gray-900 border border-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50';

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
        return <p className="text-xs text-neutral-500">Zdjęcia oryginału skasowane (retencja).</p>;
    }
    return (
        <div className="space-y-2">
            {urls.map((url, i) => (
                <a key={url} href={url} target="_blank" rel="noreferrer" className="block">
                    <img src={url} alt={`Strona ${i + 1}`} className="w-full rounded-lg border border-gray-800" />
                </a>
            ))}
            {urls.length < post.image_count && <Loader2 className="w-5 h-5 animate-spin text-neutral-500" />}
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
    if (error) return <p className="text-sm text-red-400">{error}</p>;
    if (!versions) return <Loader2 className="w-4 h-4 animate-spin text-neutral-500" />;
    return (
        <ol className="space-y-3">
            {versions.map((v) => (
                <li key={v.version} className="rounded-xl border border-gray-800 p-3 text-sm">
                    <p className="text-xs text-neutral-500">
                        v{v.version} · {VERSION_KIND[v.kind]} · {dateLabel(v.created_at)} · {v.changed_by ?? '—'}
                    </p>
                    {v.reason && <p className="text-amber-200 mt-1">Powód: {v.reason}</p>}
                    <p className="font-semibold mt-1">{v.title}</p>
                    <p className="text-neutral-400">termin: {v.event_at ? dateLabel(v.event_at) : 'brak'}</p>
                    {v.summary && <p className="text-neutral-300 mt-1">{v.summary}</p>}
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
            className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm ${mode === m ? 'bg-white/10 border-gray-600' : 'border-gray-700 hover:bg-white/5'} ${tone}`}>
            <Icon className="w-4 h-4" /> {label}
        </button>
    );

    return (
        <div className="mt-5 space-y-3">
            {post.open_requests.map((r) => (
                <div key={r.id} className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
                    <p className="font-semibold text-amber-200">
                        Sołtys prosi o {r.kind === 'correction' ? 'korektę' : 'ODWOŁANIE'} · {dateLabel(r.created_at)}
                    </p>
                    <p className="text-neutral-200 mt-1">„{r.message}”</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                        <input className={`${input} sm:max-w-xs`} placeholder="Odpowiedź dla sołtysa (opcjonalnie)"
                            value={dismissReason} onChange={(e) => setDismissReason(e.target.value)} />
                        <button onClick={() => run(() => dismissRequest(r.id, dismissReason))} disabled={busy}
                            className="rounded-xl border border-gray-700 px-3 py-1.5 text-sm hover:bg-white/5">
                            Zostaw bez zmian
                        </button>
                    </div>
                </div>
            ))}

            {post.corrected_at && (
                <p className="text-xs text-neutral-500">Ostatnia korekta: {dateLabel(post.corrected_at)} · wersja {post.version}</p>
            )}

            <div className="flex flex-wrap gap-2">
                {tab('correct', 'Popraw', PencilLine)}
                {tab('withdraw', 'Odwołaj', Ban, 'text-red-300')}
                {tab('history', 'Historia', History)}
            </div>

            {mode === 'correct' && (
                <div className="space-y-3 rounded-xl border border-gray-800 p-4">
                    <p className="text-sm text-neutral-400">
                        Tytuł, podsumowanie i przedruk poprawiasz w polach powyżej
                        {(title !== (post.title ?? '') || summary !== (post.summary ?? '') || transcript !== (post.transcript ?? ''))
                            ? ' — są zmiany w tekście.' : '.'}
                    </p>
                    <div>
                        <label className="text-xs font-bold uppercase tracking-wider text-neutral-500">Termin</label>
                        <div className="flex flex-wrap gap-3 text-sm mt-1">
                            {([['keep', 'bez zmian'], ['set', 'nowy termin'], ['clear', 'usuń termin']] as const).map(([value, label]) => (
                                <label key={value} className="inline-flex items-center gap-1.5">
                                    <input type="radio" checked={termAction === value} onChange={() => setTermAction(value)} /> {label}
                                </label>
                            ))}
                        </div>
                        {termAction === 'set' && (
                            <div className="flex flex-wrap items-center gap-2 mt-2 text-sm">
                                <input type="date" className={`${input} max-w-[11rem]`} value={day} onChange={(e) => setDay(e.target.value)} />
                                <input type="time" className={`${input} max-w-[8rem]`} value={from} onChange={(e) => setFrom(e.target.value)} />
                                <span className="text-neutral-500">–</span>
                                <input type="time" className={`${input} max-w-[8rem]`} value={to} onChange={(e) => setTo(e.target.value)} />
                                <span className="text-xs text-neutral-500">bez godziny = cały dzień</span>
                            </div>
                        )}
                        {termAction === 'set' && transcript === (post.transcript ?? '') && (
                            <p className="text-xs text-amber-300 mt-2">
                                Przedruk powyżej wciąż podaje stary termin — mieszkaniec zobaczy obie daty.
                                Dopisz w przedruku adnotację (np. „[Korekta: zebranie przeniesione na 22.10]”).
                            </p>
                        )}
                        {termAction === 'clear' && (
                            <p className="text-xs text-neutral-500 mt-1">Wydarzenie zniknie z kalendarza.</p>
                        )}
                        <p className="text-xs text-neutral-500 mt-1">
                            Teraz: {start ? (allDay ? `${start.toLocaleDateString('pl-PL')} (cały dzień)` : dateLabel(post.event_at)) : 'brak'}.
                            Zmiana terminu wróci do najbliższego briefingu z dopiskiem „korekta”.
                        </p>
                    </div>
                    <input className={input} placeholder="Powód korekty (zobaczą go mieszkańcy i sołtys)"
                        value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
                    <button onClick={submitCorrection} disabled={busy}
                        className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 px-4 py-2 text-sm font-semibold text-white">
                        <Check className="w-4 h-4" /> Opublikuj korektę
                    </button>
                </div>
            )}

            {mode === 'withdraw' && (
                <div className="space-y-3 rounded-xl border border-red-500/30 p-4">
                    <p className="text-sm text-neutral-300">
                        Ogłoszenie zniknie z wiadomości, kalendarza, briefingu i odpowiedzi asystenta.
                        Pod jego adresem zostanie informacja o odwołaniu z powodem.
                    </p>
                    <input className={input} placeholder="Powód odwołania (zobaczą go mieszkańcy i sołtys)"
                        value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
                    <button onClick={submitWithdraw} disabled={busy}
                        className="inline-flex items-center gap-2 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-40 px-4 py-2 text-sm font-semibold text-white">
                        <Ban className="w-4 h-4" /> Odwołaj ogłoszenie
                    </button>
                </div>
            )}

            {mode === 'history' && <VersionHistory postId={post.id} />}

            {error && <p className="text-sm text-red-400">{error}</p>}
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
            <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${status.tone}`}>{status.label}</span>
                <span className="text-sm font-semibold">{post.signed_as}</span>
                <span className="text-xs text-neutral-500">
                    {dateLabel(post.created_at)} · {post.author_name} ({post.author_email})
                </span>
            </div>

            {post.status === 'withdrawn' && (
                <p className="mb-3 text-sm text-red-300">Odwołane {dateLabel(post.withdrawn_at)}: {post.withdraw_reason}</p>
            )}
            {post.ai_error && (
                <p className="mb-3 text-sm text-amber-300 flex gap-2"><AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />{post.ai_error}</p>
            )}
            {!!post.personal_data?.length && (
                <div className="mb-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-200">
                    <p className="font-semibold mb-1">Dane osobowe w piśmie — sprawdź przedruk:</p>
                    <ul className="list-disc pl-5 space-y-0.5">
                        {post.personal_data.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                </div>
            )}
            {!!post.illegible?.length && (
                <p className="mb-3 text-sm text-neutral-400">Nieczytelne: {post.illegible.join('; ')}</p>
            )}
            {post.note && <p className="mb-3 text-sm text-neutral-300">Dopisek sołtysa: „{post.note}”</p>}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Oryginał (tylko redakcja)</p>
                    <PostImages post={post} />
                </div>
                <div className="space-y-3">
                    <div>
                        <label className="text-xs font-bold uppercase tracking-wider text-neutral-500">Tytuł</label>
                        <input className={input} value={title} onChange={(e) => setTitle(e.target.value)} disabled={locked} />
                    </div>
                    <div>
                        <label className="text-xs font-bold uppercase tracking-wider text-neutral-500">Podsumowanie</label>
                        <textarea className={input} rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} disabled={locked} />
                    </div>
                    <div>
                        <label className="text-xs font-bold uppercase tracking-wider text-neutral-500">Przedruk</label>
                        <textarea className={`${input} font-mono text-xs`} rows={14} value={transcript} onChange={(e) => setTranscript(e.target.value)} disabled={locked} />
                    </div>
                    <p className="text-xs text-neutral-500">
                        {post.doc_type ? `${post.doc_type} · ` : ''}
                        termin: {eventAt ? eventAt.toLocaleString('pl-PL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }) : 'brak'}
                    </p>
                </div>
            </div>

            {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

            {!decided && (
                <div className="mt-5 flex flex-wrap items-center gap-2">
                    <button onClick={approve} disabled={busy || post.status === 'processing'}
                        className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 px-4 py-2 text-sm font-semibold text-white">
                        <Check className="w-4 h-4" /> Publikuj{dirty ? ' z poprawkami' : ''}
                    </button>
                    {dirty && (
                        <button onClick={() => run(save)} disabled={busy}
                            className="rounded-xl border border-gray-700 px-4 py-2 text-sm hover:bg-white/5">Zapisz poprawki</button>
                    )}
                    <button onClick={() => run(() => rereadPost(post.id))} disabled={busy || !post.image_count}
                        className="inline-flex items-center gap-2 rounded-xl border border-gray-700 px-4 py-2 text-sm hover:bg-white/5 disabled:opacity-40">
                        <RefreshCw className="w-4 h-4" /> Odczytaj ponownie
                    </button>
                    <input className={`${input} sm:max-w-xs`} placeholder="Powód odrzucenia (trafi do sołtysa)"
                        value={reason} onChange={(e) => setReason(e.target.value)} />
                    <button onClick={() => run(() => rejectPost(post.id, reason))} disabled={busy}
                        className="inline-flex items-center gap-2 rounded-xl border border-red-500/40 text-red-300 px-4 py-2 text-sm hover:bg-red-500/10">
                        <X className="w-4 h-4" /> Odrzuć
                    </button>
                </div>
            )}
            {post.status === 'published' && <PublishedActions post={post} draft={{ title, summary, transcript }} onChanged={onChanged} />}
            {post.status === 'withdrawn' && (
                <details className="mt-4">
                    <summary className="text-sm text-neutral-400 cursor-pointer">Historia</summary>
                    <div className="mt-2"><VersionHistory postId={post.id} /></div>
                </details>
            )}
            {post.url && (
                <a href={post.url} className="mt-4 inline-block text-sm text-blue-400 hover:text-blue-300">Zobacz na stronie →</a>
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
            <div className="flex gap-2">
                {(['queue', 'all'] as const).map((f) => (
                    <button key={f} onClick={() => setFilter(f)}
                        className={`rounded-full px-4 py-1.5 text-sm ${filter === f ? 'bg-blue-600 text-white' : 'bg-white/5 text-neutral-300'}`}>
                        {f === 'queue' ? 'Do decyzji' : 'Wszystkie'}
                    </button>
                ))}
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
            {posts === null ? <Loader2 className="w-5 h-5 animate-spin text-neutral-500" /> :
                posts.length === 0 ? <p className="text-sm text-neutral-500">Nic nie czeka na decyzję.</p> :
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
                <h3 className="font-bold mb-1">Nowe zaproszenie dla sołtysa</h3>
                <p className="text-sm text-neutral-400 mb-4">
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
                        className="rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 px-4 py-2 text-sm font-semibold text-white">
                        Generuj link
                    </button>
                </div>
                {created && (
                    <div className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm">
                        <p className="text-emerald-300 font-semibold mb-1">{created.signed_as} — link gotowy</p>
                        <div className="flex gap-2 items-center">
                            <code className="flex-1 truncate text-xs text-neutral-300">{created.url}</code>
                            <button onClick={() => copy(created)} className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs inline-flex items-center gap-1">
                                <Copy className="w-3.5 h-3.5" /> {copied === created.id ? 'Skopiowano' : 'Kopiuj'}
                            </button>
                        </div>
                    </div>
                )}
                {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
            </div>

            <div className={card}>
                <h3 className="font-bold mb-3">Wystawione zaproszenia</h3>
                {invitations.length === 0 ? <p className="text-sm text-neutral-500">Brak zaproszeń.</p> : (
                    <ul className="divide-y divide-gray-800/70 text-sm">
                        {invitations.map((inv) => (
                            <li key={inv.id} className="py-3 flex flex-wrap items-center gap-2">
                                <span className="font-medium">{inv.signed_as}</span>
                                {inv.invitee_label && <span className="text-neutral-400">· {inv.invitee_label}</span>}
                                <span className="text-xs text-neutral-500">
                                    · {INVITATION_STATE[inv.state]}
                                    {inv.state === 'used' && inv.used_by_email ? ` przez ${inv.used_by_email}` : ''}
                                    {inv.state === 'active' ? ` do ${dateLabel(inv.expires_at)}` : ''}
                                </span>
                                {inv.state === 'active' && (
                                    <span className="ml-auto flex gap-2">
                                        <button onClick={() => copy(inv)} className="rounded-lg border border-gray-700 px-3 py-1 text-xs inline-flex items-center gap-1">
                                            <Copy className="w-3.5 h-3.5" /> {copied === inv.id ? 'Skopiowano' : 'Kopiuj link'}
                                        </button>
                                        <button onClick={() => revokeInvitation(inv.id).then(load).catch((e) => setError(e.message))}
                                            className="rounded-lg border border-red-500/40 text-red-300 px-3 py-1 text-xs">Wycofaj</button>
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
            <h3 className="font-bold mb-3">Sołtysi z kontem</h3>
            {error && <p className="text-sm text-red-400 mb-2">{error}</p>}
            {roles === null ? <Loader2 className="w-5 h-5 animate-spin text-neutral-500" /> :
                roles.length === 0 ? <p className="text-sm text-neutral-500">Nikt jeszcze nie przyjął zaproszenia.</p> : (
                    <ul className="divide-y divide-gray-800/70 text-sm">
                        {roles.map((r) => (
                            <li key={r.id} className="py-3 flex flex-wrap items-center gap-2">
                                <span className="font-medium">{r.signed_as}</span>
                                <span className="text-neutral-400">· {r.user_name} ({r.user_email})</span>
                                <span className="text-xs text-neutral-500">· od {dateLabel(r.verified_at)}</span>
                                <button onClick={() => revoke(r)} className="ml-auto rounded-lg border border-red-500/40 text-red-300 px-3 py-1 text-xs">
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
            <div className="flex gap-2 overflow-x-auto">
                {tabs.map((t) => (
                    <button key={t.id} onClick={() => setSection(t.id)}
                        className={`rounded-xl px-4 py-2 text-sm font-semibold whitespace-nowrap ${section === t.id ? 'bg-blue-600 text-white' : 'bg-gray-950 border border-gray-800/50 text-neutral-300'}`}>
                        {t.label}
                    </button>
                ))}
            </div>
            {section === 'posts' && <PostsSection />}
            {section === 'invitations' && <InvitationsSection />}
            {section === 'roles' && <RolesSection />}
        </div>
    );
};

export default SolectwaAdminPanel;
