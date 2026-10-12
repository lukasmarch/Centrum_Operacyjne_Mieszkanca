import React, { useState } from 'react';
import { AlertTriangle, Bell, Check } from 'lucide-react';
import { Article } from '../../types';
import { usePushNotifications } from '../../src/hooks/usePushNotifications';

/**
 * Alert dnia — jedyny głośny element trybu prostego.
 *
 * Renderowany WYŁĄCZNIE, gdy backend oznaczył wpis jako awarię „na teraz"
 * (`is_pinned` z feed_policy.is_pinned_alert) — brak awarii = brak ramki,
 * nie pusta ramka. CTA prowadzi wprost do najmocniejszego USP serwisu:
 * pushy o awariach dla wszystkich (kategoria `alerty`, plan darmowy).
 */

/** Naiwny UTC z backendu → Date (ta sama pułapka co w useDailySummary.parseUtc). */
const parseUtc = (raw?: string): Date | null => {
    if (!raw) return null;
    const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(raw);
    const parsed = new Date(hasZone ? raw : `${raw}Z`);
    return isNaN(parsed.getTime()) ? null : parsed;
};

const hm = (d: Date) => d.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' });

/**
 * „UWAGA NA JUTRO" / „UWAGA — DZIŚ" / „TRWA TERAZ" + zakres godzin do treści.
 *
 * ⚠️ `is_pinned` to NIE zawsze awaria: feed_policy przypina też obowiązujące
 * ostrzeżenia meteo (kategoria „Pogoda"). Słowo „Awaria" pada więc wyłącznie,
 * gdy potwierdza je kategoria — inaczej przy burzy plakietka by kłamała.
 */
const eventContext = (article: Article): { eyebrow: string; timeSpan: string | null } => {
    const isAwaria = (article.category || '').toLowerCase().includes('awari');
    const start = parseUtc(article.eventAt);
    if (!start) return { eyebrow: isAwaria ? 'Awaria' : 'Uwaga', timeSpan: null };

    const end = parseUtc(article.eventUntil);
    const now = new Date();
    if (end && start <= now && now <= end) {
        return { eyebrow: 'Trwa teraz', timeSpan: `do ${hm(end)}` };
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const eventDay = new Date(start);
    eventDay.setHours(0, 0, 0, 0);
    const diffDays = Math.round((eventDay.getTime() - today.getTime()) / 86_400_000);
    const day =
        diffDays === 0 ? 'Uwaga — dziś'
        : diffDays === 1 ? 'Uwaga na jutro'
        : `Uwaga: ${start.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'numeric' })}`;

    const span = end ? `${hm(start)}–${hm(end)}` : hm(start);
    return { eyebrow: day, timeSpan: span };
};

const AlertOfTheDay: React.FC<{ article: Article }> = ({ article }) => {
    const { status, subscribe } = usePushNotifications();
    const [busy, setBusy] = useState(false);
    const [justSubscribed, setJustSubscribed] = useState(false);

    const { eyebrow, timeSpan } = eventContext(article);
    // Nagłówek AI zwykle sam podaje godziny („Jutro 9:00–14:00 nie będzie prądu")
    // — wtedy własny zakres byłby drugą, inaczej sformatowaną kopią tej samej informacji
    const showTimeSpan = timeSpan && !/\d{1,2}[:.]\d{2}/.test(article.title);
    const subscribed = status === 'subscribed' || justSubscribed;

    const enableAlerts = async () => {
        setBusy(true);
        // Tylko kategoria „alerty" — obiecujemy awarie, nie zapisujemy nikogo
        // przy okazji na poranne podsumowanie (ta sama zasada co AlertPushPrompt)
        const ok = await subscribe(['alerty']);
        if (ok) setJustSubscribed(true);
        setBusy(false);
    };

    return (
        <section
            aria-label="Alert dnia"
            className="rounded-2xl border border-red-500/40 bg-red-500/[0.07] p-5 lg:flex lg:items-center lg:gap-5"
        >
            <div className="flex-1 min-w-0">
                <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-red-400">
                    <AlertTriangle size={14} aria-hidden />
                    {eyebrow}
                </p>
                <h2 className="mt-2 text-lg lg:text-xl font-bold leading-snug text-white">
                    {showTimeSpan && <span className="text-red-300">{timeSpan} · </span>}
                    {article.title}
                </h2>
            </div>

            {subscribed ? (
                <p className="mt-4 lg:mt-0 flex items-center gap-2 shrink-0 text-sm font-medium text-emerald-400">
                    <Check size={16} aria-hidden />
                    Alerty włączone — damy znać o każdej awarii
                </p>
            ) : status !== 'unsupported' && status !== 'denied' ? (
                <button
                    onClick={enableAlerts}
                    disabled={busy}
                    className="mt-4 lg:mt-0 flex w-full lg:w-auto shrink-0 min-h-[56px] items-center justify-center gap-2 rounded-xl bg-red-500 px-6 text-base font-semibold text-white transition-colors hover:bg-red-400 disabled:opacity-60"
                >
                    <Bell size={18} aria-hidden />
                    {busy ? 'Włączam…' : 'Powiadom mnie o awariach'}
                </button>
            ) : null}
        </section>
    );
};

export default AlertOfTheDay;
