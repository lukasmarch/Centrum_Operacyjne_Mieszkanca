/**
 * Baner zgody na cookies (Prawo komunikacji elektronicznej).
 *
 * Cookies niezbędne (sesja JWT) działają bez zgody. Kategorie analityczne
 * i marketingowe są obecnie nieużywane — baner zapisuje decyzję na przyszłość,
 * a ewentualne skrypty wolno uruchamiać dopiero po sprawdzeniu zgody
 * przez getCookieConsent().
 */

import React, { useEffect, useState } from 'react';
import { Tag } from './simple/tv';
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

  // Dwa przyciski decyzji wyglądają IDENTYCZNIE — „Tylko niezbędne” nie może
  // być słabszy od „Akceptuję wszystkie” (wymóg zgody dobrowolnej, bez dark patternu).
  const decision =
    'font-cond flex min-h-[48px] items-center justify-center bg-tv-paper px-5 text-[15px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-white';
  const linkBtn = 'text-tv-bluesoft underline underline-offset-4 transition-colors hover:text-white';

  return (
    // Na telefonie nad dolną belką zakładek (64 px + margines iPhone'a), żeby jej nie zasłaniać
    <div
      className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom,0px))] z-[100] lg:bottom-0"
      role="dialog"
      aria-labelledby="cookie-consent-title"
    >
      <div className="mx-auto flex max-w-3xl flex-col px-0 md:px-4">
        <Tag as="h2" className="ml-4 md:ml-0">
          <span id="cookie-consent-title">Prywatność i cookies</span>
        </Tag>
        <div className="max-h-[60vh] overflow-y-auto border-t-2 border-tv-blue bg-tv-panel p-4 md:border-x md:border-b md:border-x-tv-seam md:border-b-tv-seam md:p-5">
          <p className="max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">
            Używamy cookies niezbędnych do działania serwisu (logowanie, sesja).
            Za Twoją zgodą możemy używać także cookies funkcjonalnych i — w przyszłości —
            analitycznych. Szczegóły w{' '}
            <button onClick={() => onNavigate('cookies')} className={linkBtn}>
              Polityce cookies
            </button>{' '}
            i{' '}
            <button onClick={() => onNavigate('privacy')} className={linkBtn}>
              Polityce prywatności
            </button>.
          </p>

          {showSettings && (
            <div className="mt-3 border-t border-tv-seam pt-1">
              <label className="flex min-h-[44px] items-center gap-3 text-[15px] text-tv-muted">
                <input type="checkbox" checked disabled className="h-5 w-5 shrink-0 accent-[#1f4fff]" />
                <span><strong className="font-semibold text-white">Niezbędne</strong> — logowanie i sesja (zawsze aktywne)</span>
              </label>
              <label className="flex min-h-[44px] cursor-pointer items-center gap-3 text-[15px] text-tv-muted">
                <input
                  type="checkbox"
                  checked={analytics}
                  onChange={(e) => setAnalytics(e.target.checked)}
                  className="h-5 w-5 shrink-0 accent-[#1f4fff]"
                />
                <span><strong className="font-semibold text-white">Analityczne</strong> — statystyki użycia serwisu (obecnie nieużywane)</span>
              </label>
              <label className="flex min-h-[44px] cursor-pointer items-center gap-3 text-[15px] text-tv-muted">
                <input
                  type="checkbox"
                  checked={marketing}
                  onChange={(e) => setMarketing(e.target.checked)}
                  className="h-5 w-5 shrink-0 accent-[#1f4fff]"
                />
                <span><strong className="font-semibold text-white">Marketingowe</strong> — personalizacja treści (obecnie nieużywane)</span>
              </label>
            </div>
          )}

          <div className="mt-4 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
            <button onClick={acceptAll} className={decision}>
              Akceptuję wszystkie
            </button>
            {showSettings ? (
              <button onClick={acceptSelected} className={decision}>
                Zapisz wybrane
              </button>
            ) : (
              <button onClick={acceptNecessary} className={decision}>
                Tylko niezbędne
              </button>
            )}
            <button
              onClick={() => setShowSettings(!showSettings)}
              aria-expanded={showSettings}
              className="col-span-2 min-h-[44px] px-1 text-left text-[15px] font-bold text-tv-bluesoft transition-colors hover:text-white sm:ml-2"
            >
              {showSettings ? 'Ukryj ustawienia' : 'Ustawienia'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CookieConsent;
