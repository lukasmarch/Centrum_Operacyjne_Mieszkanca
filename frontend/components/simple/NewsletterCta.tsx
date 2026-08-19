import React, { useState } from 'react';
import { Mail, X, Bell, Sparkles, ArrowRight } from 'lucide-react';
import { useAuth } from '../../src/context/AuthContext';

/**
 * Zaproszenie do konta — jedyne miejsce na stronie głównej, w którym prosimy
 * mieszkańca o cokolwiek.
 *
 * Po co tu stoi: push dociera tylko do tego, kto zgodził się na powiadomienia
 * w przeglądarce, a serwis nie ma ŻADNEGO innego sposobu, żeby wrócić do
 * kogoś, kto raz wszedł i wyszedł. Kampania pokazała, że bloker jest po stronie
 * dystrybucji, nie produktu — droga powrotna do mieszkańca jest tu stawką.
 *
 * **Zmiana z 19.08.2026: prowadzimy przez konto, nie przez sam adres e-mail.**
 * Wcześniej kafel przyjmował adres i zapisywał na tygodniowy newsletter bez
 * zakładania konta (`POST /newsletter/subscribe`, `frequency: weekly`).
 * Mechanizm działał i działa nadal — ale zostawiał nas z adresem, do którego
 * nie da się przypisać niczego więcej: ani miejscowości, ani zgody na push,
 * ani pytań do asystenta. Sierpniowa rolka o drodze 1255N dała 3637 zasięgu
 * i trzy wejścia na stronę; przy takim ruchu decyduje, ile zostaje z jednej
 * wizyty, a konto zostawia nieporównanie więcej niż sam wpis na listę.
 *
 * Rejestracja daje 30 dni Premium bez karty (`trial_ends_at`, wygaszane przez
 * `trial_expiry_job`), więc obietnica jest prawdziwa: newsletter jest w tym
 * zawarty, a nie zamiast niego.
 *
 * ⚠️ Zapis samym adresem NIE znika z serwisu — endpoint zostaje, bo korzysta
 * z niego stopka newslettera i mail powitalny. Zmieniamy tylko to, co strona
 * główna proponuje jako pierwsze.
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
    /** Przejście do rejestracji — konto zakłada się w jednym kroku, bez karty */
    onRegister: () => void;
}

const NewsletterCta: React.FC<NewsletterCtaProps> = ({ onRegister }) => {
    const { isAuthenticated } = useAuth();
    const [dismissed, setDismissed] = useState(wasDismissed);

    // Zalogowanemu nie proponuje się założenia konta. Ustawienia newslettera
    // ma w profilu (zakładka Preferencje) — kafel byłby tu tylko szumem.
    // Dopóki kafel zbierał sam adres, sens miał dla wszystkich; od 19.08 nie
    if (isAuthenticated || dismissed) return null;

    const close = () => {
        try {
            localStorage.setItem(DISMISS_KEY, String(Date.now()));
        } catch {
            /* tryb prywatny — wróci przy następnej wizycie, trudno */
        }
        setDismissed(true);
    };

    return (
        <section
            aria-label="Załóż konto"
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
                        Wystarczy konto — zakładasz je w minutę, bez karty.
                    </p>
                </div>
            </div>

            {/* Co dokładnie dostaje mieszkaniec. Trzy rzeczy, nie lista dziesięciu:
                obietnica, której nie da się przeczytać jednym rzutem oka, nie
                działa jak obietnica */}
            <ul className="mt-3.5 space-y-1.5 pl-1">
                <li className="flex items-center gap-2 text-sm text-neutral-300">
                    <Mail size={13} className="shrink-0 text-blue-400" aria-hidden />
                    Newsletter tygodniowy w sobotę rano
                </li>
                <li className="flex items-center gap-2 text-sm text-neutral-300">
                    <Bell size={13} className="shrink-0 text-amber-400" aria-hidden />
                    Powiadomienia o awariach prądu i wody
                </li>
                <li className="flex items-center gap-2 text-sm text-neutral-300">
                    <Sparkles size={13} className="shrink-0 text-violet-400" aria-hidden />
                    30 dni Premium gratis: mail codziennie rano i asystent bez limitu
                </li>
            </ul>

            <button
                onClick={onRegister}
                className="group mt-4 flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-6 text-sm font-bold text-white transition-colors hover:bg-blue-500"
            >
                Załóż konto — 30 dni Premium gratis
                <ArrowRight size={16} aria-hidden className="transition-transform group-hover:translate-x-0.5" />
            </button>

            <p className="mt-2 text-center text-xs leading-relaxed text-neutral-600">
                Bez karty i bez zobowiązań. Po 30 dniach konto działa dalej za darmo.
            </p>
        </section>
    );
};

export default NewsletterCta;
