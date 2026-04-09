import React, { useEffect, useState } from 'react';
import { X, Download } from 'lucide-react';

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
        <div className="fixed bottom-20 left-4 right-4 z-[200] md:left-auto md:right-6 md:w-80 animate-in slide-in-from-bottom-4 duration-300">
            <div className="glass-panel rounded-2xl p-4 border border-blue-500/20 shadow-xl">
                <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                        <Download size={18} className="text-blue-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-white">Dodaj do ekranu głównego</p>
                        <p className="text-xs text-neutral-400 mt-0.5">
                            Centrum Operacyjne Rybna jako aplikacja — szybki dostęp bez przeglądarki.
                        </p>
                        <div className="flex gap-2 mt-3">
                            <button
                                onClick={handleInstall}
                                className="btn-primary text-xs py-1.5 px-3 rounded-lg"
                            >
                                Zainstaluj
                            </button>
                            <button
                                onClick={handleDismiss}
                                className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
                            >
                                Nie teraz
                            </button>
                        </div>
                    </div>
                    <button
                        onClick={handleDismiss}
                        className="text-neutral-600 hover:text-neutral-400 transition-colors flex-shrink-0"
                    >
                        <X size={14} />
                    </button>
                </div>
            </div>
        </div>
    );
};
