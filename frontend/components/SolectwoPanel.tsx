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
                Zmianę wprowadza redakcja. Na stronie ogłoszenia mieszkańcy zobaczą, kiedy i dlaczego je zmieniono.
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
        <div className="space-y-6">
            <div className="bg-gray-950 rounded-2xl p-6 sm:p-8 border border-gray-800/50">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Twoja rola</p>
                <h2 className="text-xl font-bold mt-1">{role.signed_as}</h2>
                <p className="text-sm text-neutral-400 mt-2 leading-relaxed">
                    Zrób zdjęcie pisma albo ogłoszenia i wyślij. Odczytamy treść, przygotujemy
                    przedruk i krótkie podsumowanie, a redakcja sprawdzi je przed publikacją.
                </p>
            </div>

            <div className="bg-gray-950 rounded-2xl p-6 sm:p-8 border border-gray-800/50">
                <h3 className="text-lg font-bold mb-4">Dodaj ogłoszenie</h3>

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
                        className="w-full flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-blue-500/40 bg-blue-500/5 hover:bg-blue-500/10 py-10 px-4 transition-colors"
                    >
                        <Camera className="w-10 h-10 text-blue-400" />
                        <span className="text-base font-semibold text-neutral-100">
                            Zrób zdjęcie pisma lub wybierz z galerii
                        </span>
                        <span className="text-xs text-neutral-500">do {MAX_IMAGES} stron, każda do {MAX_FILE_MB} MB</span>
                    </button>
                ) : (
                    <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
                        {previews.map((url, i) => (
                            <div key={url} className="relative aspect-[3/4] rounded-xl overflow-hidden border border-gray-800">
                                <img src={url} alt={`Strona ${i + 1}`} className="w-full h-full object-cover" />
                                <span className="absolute bottom-1 left-1 text-[10px] font-bold bg-black/70 text-white px-1.5 py-0.5 rounded">
                                    {i + 1}
                                </span>
                                <button
                                    type="button"
                                    onClick={() => removeFile(i)}
                                    aria-label={`Usuń stronę ${i + 1}`}
                                    className="absolute top-1 right-1 w-7 h-7 rounded-full bg-black/70 text-white flex items-center justify-center"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            </div>
                        ))}
                        {files.length < MAX_IMAGES && (
                            <button
                                type="button"
                                onClick={() => inputRef.current?.click()}
                                className="aspect-[3/4] rounded-xl border-2 border-dashed border-gray-700 hover:border-blue-500/60 flex flex-col items-center justify-center gap-1 text-neutral-400 text-xs"
                            >
                                <ImagePlus className="w-6 h-6" />
                                Kolejna strona
                            </button>
                        )}
                    </div>
                )}

                <label className="block mt-5 text-sm font-medium text-neutral-300" htmlFor="solectwo-note">
                    Jedno zdanie od siebie <span className="text-neutral-500 font-normal">(nieobowiązkowe)</span>
                </label>
                <textarea
                    id="solectwo-note"
                    value={note}
                    onChange={(e) => setNote(e.target.value.slice(0, NOTE_MAX))}
                    rows={2}
                    placeholder="np. Proszę o publikację do piątku"
                    className="mt-2 w-full rounded-xl bg-gray-900 border border-gray-800 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                />

                {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
                {sent && (
                    <p className="mt-4 text-sm text-emerald-300 flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
                        Wysłane. Odczytujemy pismo, potem sprawdzi je redakcja — dostaniesz maila, gdy ogłoszenie się ukaże.
                    </p>
                )}

                <button
                    type="button"
                    onClick={submit}
                    disabled={!files.length || sending}
                    className="mt-5 w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 px-6 py-3 font-semibold text-white transition-colors"
                >
                    {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    {sending ? 'Wysyłam…' : 'Wyślij do redakcji'}
                </button>

                <details className="mt-6 text-sm text-neutral-400">
                    <summary className="cursor-pointer text-neutral-300">Co warto publikować, a czego nie wysyłać</summary>
                    <ul className="mt-3 space-y-1.5 list-disc pl-5">
                        <li>Pisma i obwieszczenia urzędowe, zebrania wiejskie, fundusz sołecki.</li>
                        <li>Wydarzenia w sołectwie i utrudnienia (woda, droga, wywóz odpadów).</li>
                        <li>Nie wysyłaj list nazwisk, adresów i numerów PESEL — wycinamy dane osób prywatnych z przedruku, ale lepiej, żeby do nas nie trafiały.</li>
                        <li>Zdjęcie oryginału widzi tylko redakcja; na stronie pokazujemy przedruk.</li>
                    </ul>
                </details>
            </div>

            <div className="bg-gray-950 rounded-2xl p-6 sm:p-8 border border-gray-800/50">
                <h3 className="text-lg font-bold mb-4">Twoje ogłoszenia</h3>
                {posts.length === 0 ? (
                    <p className="text-sm text-neutral-500">Tu pojawią się wysłane ogłoszenia i ich stan.</p>
                ) : (
                    <ul className="divide-y divide-gray-800/70">
                        {posts.map((post) => {
                            const status = STATUS_LABELS[post.status];
                            return (
                                <li key={post.id} className="py-4 first:pt-0 last:pb-0">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${status.tone}`}>
                                            {post.status === 'processing' && <Loader2 className="inline w-3 h-3 mr-1 animate-spin" />}
                                            {status.label}
                                        </span>
                                        <span className="text-xs text-neutral-500">{formatDate(post.created_at)}</span>
                                    </div>
                                    <p className="mt-1.5 font-medium text-neutral-100">
                                        {post.title || 'Ogłoszenie w trakcie odczytu'}
                                    </p>
                                    {post.status === 'rejected' && post.reject_reason && (
                                        <p className="text-sm text-neutral-400 mt-1">Powód: {post.reject_reason}</p>
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
                                            className="mt-1.5 inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
                                        >
                                            Zobacz na stronie <ExternalLink className="w-3.5 h-3.5" />
                                        </a>
                                    )}
                                    {post.status === 'published' && <ChangeRequestForm post={post} onSent={loadPosts} />}
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>
        </div>
    );
};

export default SolectwoPanel;
