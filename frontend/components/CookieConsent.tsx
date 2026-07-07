/**
 * Baner zgody na cookies (Prawo komunikacji elektronicznej).
 *
 * Cookies niezbędne (sesja JWT) działają bez zgody. Kategorie analityczne
 * i marketingowe są obecnie nieużywane — baner zapisuje decyzję na przyszłość,
 * a ewentualne skrypty wolno uruchamiać dopiero po sprawdzeniu zgody
 * przez getCookieConsent().
 */

import React, { useEffect, useState } from 'react';
import { Cookie } from 'lucide-react';
import { AppSection } from '../types';

const CONSENT_KEY = 'cookie_consent_v1';
const CONSENT_MAX_AGE_MS = 365 * 24 * 60 * 60 * 1000; // 12 miesięcy — potem pytamy ponownie

export interface CookieConsentValue {
  necessary: true;
  analytics: boolean;
  marketing: boolean;
  timestamp: string;
}

export function getCookieConsent(): CookieConsentValue | null {
  try {
    const raw = localStorage.getItem(CONSENT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CookieConsentValue;
    if (Date.now() - new Date(parsed.timestamp).getTime() > CONSENT_MAX_AGE_MS) {
      return null; // zgoda wygasła — baner pojawi się ponownie
    }
    return parsed;
  } catch {
    return null;
  }
}

export function resetCookieConsent(): void {
  localStorage.removeItem(CONSENT_KEY);
}

function saveConsent(analytics: boolean, marketing: boolean): void {
  const value: CookieConsentValue = {
    necessary: true,
    analytics,
    marketing,
    timestamp: new Date().toISOString(),
  };
  localStorage.setItem(CONSENT_KEY, JSON.stringify(value));
}

interface CookieConsentProps {
  onNavigate: (section: AppSection) => void;
}

export const CookieConsent: React.FC<CookieConsentProps> = ({ onNavigate }) => {
  const [visible, setVisible] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [marketing, setMarketing] = useState(false);

  useEffect(() => {
    if (!getCookieConsent()) setVisible(true);
  }, []);

  if (!visible) return null;

  const acceptAll = () => { saveConsent(true, true); setVisible(false); };
  const acceptNecessary = () => { saveConsent(false, false); setVisible(false); };
  const acceptSelected = () => { saveConsent(analytics, marketing); setVisible(false); };

  return (
    <div className="fixed bottom-0 inset-x-0 z-[100] p-3 md:p-4" role="dialog" aria-label="Zgoda na pliki cookies">
      <div className="max-w-3xl mx-auto rounded-2xl border border-white/10 bg-gray-950/95 backdrop-blur-md shadow-2xl p-4 md:p-5">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-500/15 flex items-center justify-center shrink-0 mt-0.5">
            <Cookie size={17} className="text-blue-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white mb-1">Prywatność i cookies</p>
            <p className="text-xs text-neutral-400 leading-relaxed">
              Używamy cookies niezbędnych do działania serwisu (logowanie, sesja).
              Za Twoją zgodą możemy używać także cookies funkcjonalnych i — w przyszłości —
              analitycznych. Szczegóły w{' '}
              <button
                onClick={() => onNavigate('cookies')}
                className="text-blue-400 hover:underline"
              >
                Polityce cookies
              </button>{' '}
              i{' '}
              <button
                onClick={() => onNavigate('privacy')}
                className="text-blue-400 hover:underline"
              >
                Polityce prywatności
              </button>.
            </p>

            {showSettings && (
              <div className="mt-3 space-y-2 border-t border-white/5 pt-3">
                <label className="flex items-center gap-2.5 text-xs text-neutral-400">
                  <input type="checkbox" checked disabled className="accent-blue-500" />
                  <span><strong className="text-neutral-200">Niezbędne</strong> — logowanie i sesja (zawsze aktywne)</span>
                </label>
                <label className="flex items-center gap-2.5 text-xs text-neutral-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={analytics}
                    onChange={(e) => setAnalytics(e.target.checked)}
                    className="accent-blue-500"
                  />
                  <span><strong className="text-neutral-200">Analityczne</strong> — statystyki użycia serwisu (obecnie nieużywane)</span>
                </label>
                <label className="flex items-center gap-2.5 text-xs text-neutral-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={marketing}
                    onChange={(e) => setMarketing(e.target.checked)}
                    className="accent-blue-500"
                  />
                  <span><strong className="text-neutral-200">Marketingowe</strong> — personalizacja treści (obecnie nieużywane)</span>
                </label>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2 mt-3">
              <button
                onClick={acceptAll}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition-colors"
              >
                Akceptuję wszystkie
              </button>
              {showSettings ? (
                <button
                  onClick={acceptSelected}
                  className="px-4 py-2 rounded-xl bg-white/8 hover:bg-white/12 border border-white/10 text-white text-xs font-bold transition-colors"
                >
                  Zapisz wybrane
                </button>
              ) : (
                <button
                  onClick={acceptNecessary}
                  className="px-4 py-2 rounded-xl bg-white/8 hover:bg-white/12 border border-white/10 text-white text-xs font-bold transition-colors"
                >
                  Tylko niezbędne
                </button>
              )}
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="px-3 py-2 text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
              >
                {showSettings ? 'Ukryj ustawienia' : 'Ustawienia'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CookieConsent;
