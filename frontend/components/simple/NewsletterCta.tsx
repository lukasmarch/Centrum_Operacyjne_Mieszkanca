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
        <section aria-label="Załóż konto" className="relative">
            <div className="relative border-t-2 border-tv-paper bg-tv-panel p-4 pr-12 lg:flex lg:items-center lg:gap-8 lg:p-5 lg:pr-14">
                <button
                    onClick={close}
                    aria-label="Nie teraz — schowaj na dwa miesiące"
                    className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center text-tv-muted transition-colors hover:text-white"
                >
                    <X size={18} aria-hidden />
                </button>

                <div className="min-w-0 flex-1">
                    <h2 className="font-cond text-[22px] font-extrabold leading-snug text-white">
                        Podsumowanie tygodnia w sobotę rano na maila
                    </h2>
                    {/* Trzy rzeczy, nie dziesięć: obietnica ma się dać przeczytać
                        jednym rzutem oka — i każda ma pokrycie w kodzie (CLAUDE.md,
                        „Obietnice oferty a kod”) */}
                    <ul className="mt-2 space-y-1 text-[15px] leading-snug text-[#d7dbe8]">
                        <li className="flex items-start gap-2"><Mail size={15} className="mt-0.5 shrink-0 text-tv-muted" aria-hidden />Newsletter tygodniowy w sobotę rano</li>
                        <li className="flex items-start gap-2"><Bell size={15} className="mt-0.5 shrink-0 text-tv-muted" aria-hidden />Powiadomienia o awariach prądu i wody</li>
                        <li className="flex items-start gap-2"><Sparkles size={15} className="mt-0.5 shrink-0 text-tv-muted" aria-hidden />30 dni Premium gratis: mail codziennie rano i asystent bez limitu</li>
                    </ul>
                </div>

                <div className="mt-4 shrink-0 lg:mt-0 lg:w-[300px]">
                    <button
                        onClick={onRegister}
                        className="font-cond group flex min-h-[52px] w-full items-center justify-center gap-2 bg-tv-paper px-6 text-[18px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-white"
                    >
                        Załóż konto
                        <ArrowRight size={18} aria-hidden className="transition-transform group-hover:translate-x-0.5" />
                    </button>
                    <p className="mt-2 text-center text-[14px] leading-snug text-tv-muted">
                        W minutę, bez karty. Po 30 dniach konto działa dalej za darmo.
                    </p>
                </div>
            </div>
        </section>
    );
};

export default NewsletterCta;
