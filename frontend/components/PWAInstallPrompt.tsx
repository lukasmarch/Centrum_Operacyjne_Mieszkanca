import React, { useEffect, useState } from 'react';
import { X, Download } from 'lucide-react';
import { Tag } from './simple/tv';

const VISIT_KEY = 'pwa_visit_count';
const DISMISSED_KEY = 'pwa_install_dismissed';
const INSTALLED_KEY = 'pwa_installed';
const MIN_VISITS = 3;

interface BeforeInstallPromptEvent extends Event {
    prompt(): Promise<void>;
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export const PWAInstallPrompt: React.FC = () => {
    const [show, setShow] = useState(false);
    const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);

    useEffect(() => {
        // Count this visit
        const count = parseInt(localStorage.getItem(VISIT_KEY) || '0', 10) + 1;
        localStorage.setItem(VISIT_KEY, String(count));

        const dismissed = localStorage.getItem(DISMISSED_KEY);
        const installed = localStorage.getItem(INSTALLED_KEY);

        if (installed || dismissed) return;

        const handler = (e: Event) => {
            e.preventDefault();
            setDeferredPrompt(e as BeforeInstallPromptEvent);
            if (count >= MIN_VISITS) {
                setShow(true);
            }
        };

        window.addEventListener('beforeinstallprompt', handler);
        window.addEventListener('appinstalled', () => {
            localStorage.setItem(INSTALLED_KEY, '1');
            setShow(false);
        });

        // Show if we already have the deferred prompt and enough visits
        if (count >= MIN_VISITS) {
            // Will show when beforeinstallprompt fires
        }

        return () => window.removeEventListener('beforeinstallprompt', handler);
    }, []);

    const handleInstall = async () => {
        if (!deferredPrompt) return;
        await deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {
            localStorage.setItem(INSTALLED_KEY, '1');
        } else {
            localStorage.setItem(DISMISSED_KEY, '1');
        }
        setShow(false);
        setDeferredPrompt(null);
    };

    const handleDismiss = () => {
        localStorage.setItem(DISMISSED_KEY, '1');
        setShow(false);
    };

    if (!show) return null;

    return (
        // Płaski panel nad dolną belką zakładek (telefon); na desktopie w prawym dolnym rogu
        <div
            role="dialog"
            aria-labelledby="pwa-install-title"
            className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom,0px))] z-[200] flex flex-col lg:inset-x-auto lg:bottom-6 lg:right-6 lg:w-96"
        >
            <Tag as="h2" className="ml-4 lg:ml-0">
                <span id="pwa-install-title">Dodaj do ekranu głównego</span>
            </Tag>
            <div className="flex items-start gap-2 border-t-2 border-tv-blue bg-tv-panel py-3 pl-4 pr-1 lg:border-x lg:border-b lg:border-x-tv-seam lg:border-b-tv-seam">
                <div className="min-w-0 flex-1">
                    <p className="text-[15px] leading-snug text-[#d7dbe8]">
                        Centrum Operacyjne Rybna jako aplikacja — szybki dostęp bez przeglądarki.
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                        <button
                            onClick={handleInstall}
                            className="font-cond inline-flex min-h-[44px] items-center gap-2 bg-tv-blue px-4 text-[15px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff]"
                        >
                            <Download size={16} aria-hidden />
                            Zainstaluj
                        </button>
                        <button
                            onClick={handleDismiss}
                            className="min-h-[44px] px-2 text-[15px] font-bold text-tv-bluesoft transition-colors hover:text-white"
                        >
                            Nie teraz
                        </button>
                    </div>
                </div>
                <button
                    onClick={handleDismiss}
                    aria-label="Zamknij"
                    className="flex h-11 w-11 shrink-0 items-center justify-center text-tv-muted transition-colors hover:text-white"
                >
                    <X size={18} />
                </button>
            </div>
        </div>
    );
};
