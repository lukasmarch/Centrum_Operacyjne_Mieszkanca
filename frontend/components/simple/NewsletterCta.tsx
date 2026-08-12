import React, { useState } from 'react';
import { Mail, Check, X } from 'lucide-react';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Zapis na tygodniowy newsletter — jedyny punkt na stronie głównej, w którym
 * prosimy o adres e-mail.
 *
 * Po co tu stoi: push dociera tylko do tego, kto zgodził się na powiadomienia
 * w przeglądarce, a serwis nie ma ŻADNEGO innego sposobu, żeby wrócić do
 * mieszkańca, który raz wszedł i wyszedł. Kampania pokazała, że bloker jest
 * po stronie dystrybucji, nie produktu — adres e-mail to druga (i jedyna
 * pozostała) droga powrotna.
 *
 * Dlaczego akurat tygodniowy: `POST /api/newsletter/subscribe` przyjmuje
 * `weekly` od każdego, także bez konta; `daily` wymaga Premium i zwróciłby 403.
 * Zapis tutaj NIE zakłada konta i nie prowadzi do płatności — prośba o pieniądze
 * na stronie głównej kosztowałaby więcej zaufania, niż warta jest konwersja.
 *
 * RODO: backend wysyła mail z potwierdzeniem (double opt-in), więc sam wpis
 * w formularzu nikogo jeszcze nie zapisuje; link do polityki prywatności
 * i informacja o wypisie stoją przy przycisku, nie w stopce.
 */

const DISMISS_KEY = 'rl_newsletter_cta_dismissed_at';
const DISMISS_DAYS = 60;

const wasDismissed = (): boolean => {
    try {
        const raw = localStorage.getItem(DISMISS_KEY);
        if (!raw) return false;
        return (Date.now() - Number(raw)) / 86_400_000 < DISMISS_DAYS;
    } catch {
        return false;
    }
};

interface NewsletterCtaProps {
    /** Miejscowość mieszkańca — backend trzyma ją przy zapisie (pole `location`) */
    town: string;
    onOpenPrivacy: () => void;
}

const NewsletterCta: React.FC<NewsletterCtaProps> = ({ town, onOpenPrivacy }) => {
    const [email, setEmail] = useState('');
    const [state, setState] = useState<'idle' | 'busy' | 'done' | 'error'>('idle');
    const [message, setMessage] = useState('');
    const [dismissed, setDismissed] = useState(wasDismissed);

    if (dismissed) return null;

    const close = () => {
        try {
            localStorage.setItem(DISMISS_KEY, String(Date.now()));
        } catch {
            /* tryb prywatny — wróci przy następnej wizycie, trudno */
        }
        setDismissed(true);
    };

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        const address = email.trim();
        if (!address) return;

        setState('busy');
        try {
            const res = await fetch(`${API_URL}/newsletter/subscribe`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: address, frequency: 'weekly', location: town }),
            });

            if (res.ok) {
                // Zapamiętujemy zapis — inaczej ten sam baner witałby przy każdym
                // wejściu kogoś, kto właśnie podał adres
                setState('done');
                try {
                    localStorage.setItem(DISMISS_KEY, String(Date.now()));
                } catch { /* bez zapamiętania, ale zapis się udał */ }
                return;
            }

            // 400 = adres już zapisany. To nie jest błąd użytkownika i nie ma
            // powodu, żeby brzmiało jak awaria
            const detail = (await res.json().catch(() => null))?.detail as string | undefined;
            setState('error');
            setMessage(
                res.status === 400 && detail?.includes('already')
                    ? 'Ten adres jest już zapisany — sprawdź skrzynkę.'
                    : 'Nie udało się zapisać. Spróbuj proszę za chwilę.',
            );
        } catch {
            setState('error');
            setMessage('Brak połączenia z serwerem. Spróbuj proszę za chwilę.');
        }
    };

    if (state === 'done') {
        return (
            <section
                aria-label="Zapis na newsletter"
                className="flex items-center gap-2.5 rounded-2xl border border-emerald-800/30 bg-emerald-950/30 p-4 text-sm text-emerald-300"
            >
                <Check size={16} className="shrink-0" aria-hidden />
                Sprawdź skrzynkę — wysłaliśmy link, który potwierdza zapis.
            </section>
        );
    }

    return (
        <section
            aria-label="Zapis na newsletter"
            className="relative rounded-2xl border border-white/10 bg-[#0d1117] p-5"
        >
            <button
                onClick={close}
                aria-label="Zamknij"
                className="absolute right-2.5 top-2.5 rounded-lg p-1 text-neutral-600 transition-colors hover:bg-white/5 hover:text-neutral-300"
            >
                <X size={14} aria-hidden />
            </button>

            <div className="flex items-start gap-3 pr-6">
                <Mail size={18} className="mt-0.5 shrink-0 text-blue-400" aria-hidden />
                <div className="min-w-0">
                    <h2 className="text-base font-bold text-white">
                        Podsumowanie tygodnia na maila
                    </h2>
                    <p className="mt-0.5 text-sm leading-relaxed text-neutral-400">
                        W sobotę rano jeden mail: co się działo w gminie i co przed nami.
                        Za darmo, bez zakładania konta.
                    </p>
                </div>
            </div>

            <form onSubmit={submit} className="mt-4 flex flex-col gap-2 sm:flex-row">
                <input
                    type="email"
                    required
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="twoj@email.pl"
                    aria-label="Twój adres e-mail"
                    className="min-h-[48px] min-w-0 flex-1 rounded-xl border border-white/10 bg-[#020617] px-4 text-base text-white outline-none transition-colors placeholder:text-neutral-600 focus:border-blue-500/60"
                />
                <button
                    type="submit"
                    disabled={state === 'busy'}
                    className="min-h-[48px] shrink-0 rounded-xl bg-blue-600 px-6 text-sm font-bold text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
                >
                    {state === 'busy' ? 'Zapisuję…' : 'Zapisz mnie'}
                </button>
            </form>

            {state === 'error' && (
                <p className="mt-2 text-xs text-amber-400">{message}</p>
            )}

            <p className="mt-2 text-xs leading-relaxed text-neutral-600">
                Wypisujesz się jednym kliknięciem w stopce każdego maila.{' '}
                <button onClick={onOpenPrivacy} className="underline hover:text-neutral-400">
                    Polityka prywatności
                </button>
            </p>
        </section>
    );
};

export default NewsletterCta;
