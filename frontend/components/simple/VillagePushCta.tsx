import React, { useEffect, useState } from 'react';
import { Bell, BellRing, Check, X } from 'lucide-react';
import { usePushNotifications } from '../../src/hooks/usePushNotifications';
import { track } from '../../src/services/analytics';
import { aboutPlace, inPlace } from '../../src/utils/placeLocative';

/**
 * Prośba o powiadomienia — o TWOJEJ wsi, zaraz pod belką.
 *
 * Pomiar przed odświeżeniem: 73 wyświetlenia szarego banera, 0 kliknięć.
 * Baner stał piąty na stronie, miał przycisk 12 px i gołą listę 22 wsi bez
 * etykiety. Teraz pytanie pada w miejscu, gdzie odpowiedź jest oczywista
 * (pod stanem prądu i wody), a wieś jest już wybrana albo da się ją wybrać
 * jednym dotknięciem w główce.
 *
 * Obietnica zostaje wąska jak dotąd: kategoria `alerty` (prąd, woda, pożar,
 * wypadek), wieś zapisana na SUBSKRYPCJI — konto nie jest potrzebne.
 * Klucz zamknięcia ten sam co w `AlertPushPrompt`, żeby zamknięcie jednego
 * nie wywoływało drugiego.
 */
const DISMISS_KEY = 'rl_push_prompt_dismissed_at';
const DISMISS_DAYS = 30;

const wasDismissed = (): boolean => {
    try {
        const raw = localStorage.getItem(DISMISS_KEY);
        return raw ? (Date.now() - Number(raw)) / 86_400_000 < DISMISS_DAYS : false;
    } catch {
        return false;
    }
};

interface VillagePushCtaProps {
    village: string | null;
    onPickVillage: () => void;
}

const VillagePushCta: React.FC<VillagePushCtaProps> = ({ village, onPickVillage }) => {
    const { status, isSubscribed, isSupported, subscribe } = usePushNotifications();
    const [dismissed, setDismissed] = useState(wasDismissed);
    const [busy, setBusy] = useState(false);
    const [justEnabled, setJustEnabled] = useState(false);

    const hidden = dismissed || !isSupported || status === 'denied' || status === 'loading' || status === 'unsupported';
    const where = village ? inPlace(village) : 'w gminie Rybno';

    useEffect(() => {
        if (!hidden && !isSubscribed && !justEnabled) track('push_prompt');
    }, [hidden, isSubscribed, justEnabled]);

    if (isSubscribed || justEnabled) {
        return (
            <p className="flex items-center gap-2 border-b border-tv-seam py-2.5 text-[15px] text-tv-muted">
                <Check size={17} className="shrink-0 text-tv-green" aria-hidden />
                {justEnabled
                    ? <>Gotowe — o następnej awarii {where} dowiesz się od razu.</>
                    : <>Powiadomienia o awariach są włączone na tym urządzeniu.</>}
            </p>
        );
    }
    if (hidden) return null;

    const enable = async () => {
        setBusy(true);
        const ok = await subscribe(['alerty'], village || undefined);
        setBusy(false);
        if (ok) setJustEnabled(true);
    };

    const close = () => {
        try {
            localStorage.setItem(DISMISS_KEY, String(Date.now()));
        } catch {
            /* tryb prywatny — wróci przy następnej wizycie */
        }
        setDismissed(true);
    };

    return (
        <section aria-label="Powiadomienia o awariach" className="relative bg-tv-panel p-4 pr-12 lg:flex lg:items-center lg:gap-6 lg:pr-14">
            <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-[17px] font-bold leading-snug text-white">
                    <BellRing size={18} className="shrink-0 text-tv-yellow" aria-hidden />
                    Dowiedz się o awarii {where}, zanim wejdziesz na stronę
                </p>
                <p className="mt-1 text-[15px] leading-snug text-tv-muted">
                    Prąd, woda, pożar, wypadek — nic poza tym. Za darmo, bez konta.
                    {!village && (
                        <>
                            {' '}
                            <button onClick={onPickVillage} className="font-semibold text-tv-bluesoft underline underline-offset-2 hover:text-white">
                                Tylko o mojej wsi
                            </button>
                        </>
                    )}
                </p>
            </div>
            <button
                onClick={enable}
                disabled={busy}
                className="font-cond mt-3 flex min-h-[52px] w-full shrink-0 items-center justify-center gap-2 bg-tv-blue whitespace-nowrap px-4 text-[17px] font-extrabold uppercase tracking-normal text-white transition-colors hover:bg-[#3a63ff] disabled:opacity-60 sm:px-6 sm:text-[18px] sm:tracking-wide lg:mt-0 lg:w-auto"
            >
                <Bell size={18} aria-hidden />
                {busy ? 'Włączam…' : village ? `Powiadamiaj ${aboutPlace(village)}` : 'Włącz powiadomienia'}
            </button>
            <button
                onClick={close}
                aria-label="Nie teraz — schowaj na miesiąc"
                className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center text-tv-muted hover:text-white"
            >
                <X size={18} aria-hidden />
            </button>
        </section>
    );
};

export default VillagePushCta;
