/**
 * Panel sołtysa — „Dodaj ogłoszenie": zdjęcie pisma i wyślij.
 *
 * Zasada: sołtys nie zmienia nawyku z Facebooka. Jeden przycisk otwiera aparat
 * albo galerię (bez `capture`, żeby telefon dał wybór), kolejne strony dokłada
 * tym samym przyciskiem. Resztę — odczyt, przedruk, podsumowanie — robimy my,
 * a redakcja sprawdza przed publikacją.
 *
 * Po publikacji sołtys nie edytuje sam: prosi o korektę albo odwołanie,
 * a zmienia redakcja (E7) — ta sama bramka co przy pierwszej wersji.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, CheckCircle2, ExternalLink, ImagePlus, Loader2, PencilLine, Send, X } from 'lucide-react';
import { Notice, Tag, TagTone } from './simple/tv';
import {
    ChangeKind, MyPost, MyRole, STATUS_LABELS, createPost, fetchMyPosts, parseUtc, requestChange,
} from '../src/services/solectwaApi';

// Te same limity co backend (`api/endpoints/solectwa.py`) — tu tylko po to,
// żeby nie wysyłać 30 MB, które serwer i tak odrzuci
const MAX_IMAGES = 5;
const MAX_FILE_MB = 10;
const NOTE_MAX = 500;

interface Props {
    role: MyRole;
}

const POST_TONE: Partial<Record<MyPost['status'], TagTone>> = {
    processing: 'seam',
    pending: 'yellow',
    failed: 'yellow',
    published: 'blue',
    rejected: 'seam',
};

const formatDate = (value: string | null) => {
    const d = parseUtc(value);
    return d
        ? d.toLocaleString('pl-PL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
        : '';
};

const REQUEST_LABEL: Record<ChangeKind, string> = {
    correction: 'Prośba o poprawkę',
    withdrawal: 'Prośba o odwołanie',
};

/** Prośba o poprawkę albo odwołanie opublikowanego ogłoszenia. */
const ChangeRequestForm: React.FC<{ post: MyPost; onSent: () => void }> = ({ post, onSent }) => {
    const [open, setOpen] = useState(false);
    const [kind, setKind] = useState<ChangeKind>('correction');
    const [message, setMessage] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    if (post.open_requests.length > 0) {
        return (
            <div className="mt-2 space-y-1">
                {post.open_requests.map((r) => (
                    <p key={r.id} className="text-sm text-amber-300">
                        {REQUEST_LABEL[r.kind]} czeka na redakcję: „{r.message}”
                    </p>
                ))}
            </div>
        );
    }
    if (!open) {
        return (
            <button onClick={() => setOpen(true)}
                className="mt-1.5 ml-4 inline-flex items-center gap-1 text-sm text-neutral-400 hover:text-neutral-200">
                <PencilLine className="w-3.5 h-3.5" /> Poprawka lub odwołanie
            </button>
        );
    }

    const send = async () => {
        if (message.trim().length < 5) {
            setError('Napisz w kilku słowach, co zmienić.');
            return;
        }
        setBusy(true);
        setError('');
        try {
            await requestChange(post.id, kind, message);
            setOpen(false);
            setMessage('');
            onSent();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Nie udało się wysłać');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="mt-3 rounded-xl border border-gray-800 p-3 space-y-2">
            <div className="flex gap-2">
                {(['correction', 'withdrawal'] as const).map((k) => (
                    <button key={k} onClick={() => setKind(k)}
                        className={`rounded-full px-3 py-1 text-sm ${kind === k ? 'bg-blue-600 text-white' : 'bg-white/5 text-neutral-300'}`}>
                        {k === 'correction' ? 'Popraw' : 'Odwołaj'}
                    </button>
                ))}
            </div>
            <textarea
                className="w-full rounded-xl bg-gray-900 border border-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                rows={3}
                maxLength={1000}
                placeholder={kind === 'correction'
                    ? 'Co poprawić? Np. zebranie przeniesione na 22 października, godz. 18:00'
                    : 'Dlaczego odwołać? Np. zebranie się nie odbędzie'}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
            />
            <p className="text-xs text-neutral-500">
                Zmianę wprowadza redakcja. Mieszkańcy nie zobaczą ani prośby, ani powodu — to zostaje między Tobą a redakcją.
            </p>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <div className="flex gap-2">
                <button onClick={send} disabled={busy}
                    className="inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 px-4 py-2 text-sm font-semibold text-white">
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Wyślij prośbę
                </button>
                <button onClick={() => setOpen(false)} className="rounded-xl border border-gray-700 px-4 py-2 text-sm hover:bg-white/5">
                    Anuluj
                </button>
            </div>
        </div>
    );
};

const SolectwoPanel: React.FC<Props> = ({ role }) => {
    const [files, setFiles] = useState<File[]>([]);
    const [previews, setPreviews] = useState<string[]>([]);
    const [note, setNote] = useState('');
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');
    const [sent, setSent] = useState(false);
    const [posts, setPosts] = useState<MyPost[]>([]);
    const inputRef = useRef<HTMLInputElement>(null);

    const loadPosts = useCallback(() => {
        fetchMyPosts().then(setPosts).catch(() => {});
    }, []);

    useEffect(() => { loadPosts(); }, [loadPosts]);

    // Odczyt pisma trwa kilkanaście sekund — odświeżamy listę, dopóki coś się czyta
    useEffect(() => {
        if (!posts.some((p) => p.status === 'processing')) return;
        const timer = window.setTimeout(loadPosts, 4000);
        return () => window.clearTimeout(timer);
    }, [posts, loadPosts]);

    useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

    const addFiles = (list: FileList | null) => {
        if (!list) return;
        setError('');
        setSent(false);
        const incoming = Array.from(list).filter((f) => f.type.startsWith('image/'));
        const tooBig = incoming.find((f) => f.size > MAX_FILE_MB * 1024 * 1024);
        if (tooBig) {
            setError(`Zdjęcie „${tooBig.name}” jest za duże (limit ${MAX_FILE_MB} MB).`);
            return;
        }
        const next = [...files, ...incoming].slice(0, MAX_IMAGES);
        if (files.length + incoming.length > MAX_IMAGES) {
            setError(`Najwyżej ${MAX_IMAGES} stron w jednym ogłoszeniu.`);
        }
        previews.forEach((url) => URL.revokeObjectURL(url));
        setFiles(next);
        setPreviews(next.map((f) => URL.createObjectURL(f)));
        if (inputRef.current) inputRef.current.value = '';
    };

    const removeFile = (index: number) => {
        const next = files.filter((_, i) => i !== index);
        previews.forEach((url) => URL.revokeObjectURL(url));
        setFiles(next);
        setPreviews(next.map((f) => URL.createObjectURL(f)));
    };

    const submit = async () => {
        if (!files.length) return;
        setSending(true);
        setError('');
        try {
            await createPost(files, note, role.id);
            previews.forEach((url) => URL.revokeObjectURL(url));
            setFiles([]);
            setPreviews([]);
            setNote('');
            setSent(true);
            loadPosts();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Nie udało się wysłać. Spróbuj ponownie.');
        } finally {
            setSending(false);
        }
    };

    return (
        <div className="space-y-6 lg:space-y-8">
            {/* Bez kickera „Twoja rola” nad nazwą — słowo przeszło do plakietki */}
            <section>
                <Tag as="h2">Twoja rola</Tag>
                <div className="border-t-2 border-tv-blue bg-tv-panel p-5 sm:p-6">
                    <p className="font-cond text-[22px] font-extrabold leading-snug text-white">{role.signed_as}</p>
                    <p className="mt-2 max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">
                        Zrób zdjęcie pisma albo ogłoszenia i wyślij. Odczytamy treść, przygotujemy
                        przedruk i krótkie podsumowanie, a redakcja sprawdzi je przed publikacją.
                    </p>
                </div>
            </section>

            <section>
                <Tag as="h2">Dodaj ogłoszenie</Tag>
                <div className="border-t-2 border-tv-blue bg-tv-panel p-5 sm:p-6">
                <input
                    ref={inputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={(e) => addFiles(e.target.files)}
                />

                {files.length === 0 ? (
                    <button
                        type="button"
                        onClick={() => inputRef.current?.click()}
                        className="flex w-full flex-col items-center justify-center gap-3 border-2 border-dashed border-tv-muted bg-tv-ink px-4 py-10 transition-colors hover:border-tv-paper hover:bg-tv-panel2"
                    >
                        <Camera className="h-10 w-10 text-tv-paper" aria-hidden />
                        <span className="text-[16px] font-semibold text-white">
                            Zrób zdjęcie pisma lub wybierz z galerii
                        </span>
                        <span className="tabular text-[13px] text-tv-muted">do {MAX_IMAGES} stron, każda do {MAX_FILE_MB} MB</span>
                    </button>
                ) : (
                    <div className="grid grid-cols-3 gap-px bg-tv-seam sm:grid-cols-5">
                        {previews.map((url, i) => (
                            <div key={url} className="relative aspect-[3/4] overflow-hidden bg-tv-ink">
                                <img src={url} alt={`Strona ${i + 1}`} className="h-full w-full object-cover" />
                                <span className="font-cond tabular absolute bottom-0 left-0 bg-tv-ink px-2 py-1 text-[13px] font-extrabold leading-none text-white">
                                    {i + 1}
                                </span>
                                <button
                                    type="button"
                                    onClick={() => removeFile(i)}
                                    aria-label={`Usuń stronę ${i + 1}`}
                                    className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center bg-tv-ink/85 text-white transition-colors hover:bg-tv-ink"
                                >
                                    <X className="h-5 w-5" aria-hidden />
                                </button>
                            </div>
                        ))}
                        {files.length < MAX_IMAGES && (
                            <button
                                type="button"
                                onClick={() => inputRef.current?.click()}
                                className="flex aspect-[3/4] flex-col items-center justify-center gap-1 bg-tv-ink text-[13px] text-tv-paper transition-colors hover:bg-tv-panel2"
                            >
                                <ImagePlus className="h-6 w-6 text-tv-muted" aria-hidden />
                                Kolejna strona
                            </button>
                        )}
                    </div>
                )}

                <label className="mt-5 block text-[15px] font-semibold text-tv-paper" htmlFor="solectwo-note">
                    Jedno zdanie od siebie <span className="font-normal text-tv-muted">(nieobowiązkowe)</span>
                </label>
                <textarea
                    id="solectwo-note"
                    value={note}
                    onChange={(e) => setNote(e.target.value.slice(0, NOTE_MAX))}
                    rows={2}
                    placeholder="np. Proszę o publikację do piątku"
                    className="mt-1.5 w-full border-2 border-tv-seam bg-tv-ink px-4 py-3 text-[16px] text-white outline-none transition-colors placeholder:text-tv-muted focus:border-tv-paper"
                />

                {error && <div className="mt-4"><Notice tone="warn" role="alert">{error}</Notice></div>}
                {sent && (
                    <p role="status" className="mt-4 flex items-start gap-2 text-[15px] text-tv-paper">
                        <CheckCircle2 className="mt-0.5 h-[18px] w-[18px] shrink-0 text-tv-green" aria-hidden />
                        Wysłane. Odczytujemy pismo, potem sprawdzi je redakcja — dostaniesz maila, gdy ogłoszenie się ukaże.
                    </p>
                )}

                <button
                    type="button"
                    onClick={submit}
                    disabled={!files.length || sending}
                    className="font-cond mt-5 inline-flex min-h-[52px] w-full items-center justify-center gap-2 bg-tv-blue px-6 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-tv-blue sm:w-auto"
                >
                    {!sending && <Send className="h-[18px] w-[18px]" aria-hidden />}
                    {sending ? 'Wysyłam…' : 'Wyślij do redakcji'}
                </button>

                <details className="mt-6 border-t border-tv-seam pt-2 text-[15px] text-[#d7dbe8]">
                    <summary className="flex min-h-[44px] cursor-pointer items-center font-bold text-tv-bluesoft hover:text-white">Co warto publikować, a czego nie wysyłać</summary>
                    <ul className="mt-2 list-disc space-y-1.5 pl-5 leading-relaxed">
                        <li>Pisma i obwieszczenia urzędowe, zebrania wiejskie, fundusz sołecki.</li>
                        <li>Wydarzenia w sołectwie i utrudnienia (woda, droga, wywóz odpadów).</li>
                        <li>Nie wysyłaj list nazwisk, adresów i numerów PESEL — wycinamy dane osób prywatnych z przedruku, ale lepiej, żeby do nas nie trafiały.</li>
                        <li>Zdjęcie oryginału widzi tylko redakcja; na stronie pokazujemy przedruk.</li>
                    </ul>
                </details>
                </div>
            </section>

            <section>
                <Tag as="h2" tone="seam">Twoje ogłoszenia</Tag>
                {posts.length === 0 ? (
                    <div className="border-t-2 border-tv-seam"><Notice>Tu pojawią się wysłane ogłoszenia i ich stan.</Notice></div>
                ) : (
                    <ul className="grid gap-px border-t-2 border-tv-seam bg-tv-seam">
                        {posts.map((post) => {
                            const status = STATUS_LABELS[post.status];
                            return (
                                <li key={post.id} className="bg-tv-panel px-5 py-4 sm:px-6">
                                    <div className="flex flex-wrap items-center gap-2">
                                        {/* Kolor stanu liczony tu, nie z `STATUS_LABELS.tone`
                                            (klasy starego świata): czeka = żółć, opublikowane = chaber */}
                                        <Tag tone={POST_TONE[post.status] ?? 'seam'}>{status.label}</Tag>
                                        <span className="tabular text-[13px] text-tv-muted">{formatDate(post.created_at)}</span>
                                    </div>
                                    <p className="mt-1.5 text-[16px] font-semibold text-white">
                                        {post.title || 'Ogłoszenie w trakcie odczytu'}
                                    </p>
                                    {post.status === 'rejected' && post.reject_reason && (
                                        <p className="mt-1 text-[15px] text-[#d7dbe8]">Powód: {post.reject_reason}</p>
                                    )}
                                    {post.status === 'withdrawn' && post.withdraw_reason && (
                                        <p className="text-sm text-neutral-400 mt-1">Odwołane: {post.withdraw_reason}</p>
                                    )}
                                    {post.status === 'published' && post.corrected_at && (
                                        <p className="text-xs text-neutral-500 mt-1">Poprawione {formatDate(post.corrected_at)}</p>
                                    )}
                                    {post.url && (
                                        <a
                                            href={post.url}
                                            className="mt-1 inline-flex min-h-[44px] items-center gap-1 text-[15px] font-bold text-tv-bluesoft underline-offset-4 hover:text-white hover:underline"
                                        >
                                            Zobacz na stronie <ExternalLink className="h-4 w-4" aria-hidden />
                                        </a>
                                    )}
                                    {post.status === 'published' && <ChangeRequestForm post={post} onSent={loadPosts} />}
                                </li>
                            );
                        })}
                    </ul>
                )}
            </section>
        </div>
    );
};

export default SolectwoPanel;
