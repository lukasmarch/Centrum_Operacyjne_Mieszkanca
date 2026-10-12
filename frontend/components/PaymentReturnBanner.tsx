import React, { useEffect, useState } from 'react';
import { CheckCircle, Clock, XCircle, X, RefreshCw } from 'lucide-react';
import { getAccessToken } from '../src/services/authApi';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

type VerifyState = 'checking' | 'success' | 'pending' | 'failed' | null;

/**
 * Baner statusu płatności po powrocie z Przelewy24.
 * P24 przekierowuje na {APP_URL}/payment/success?session=COM-... — Caddy serwuje SPA
 * (try_files → index.html), a ten komponent odczytuje session z URL, weryfikuje
 * transakcję w API i pokazuje wynik. URL jest czyszczony przez history.replaceState.
 */
export const PaymentReturnBanner: React.FC = () => {
  const [state, setState] = useState<VerifyState>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get('session');
    const isPaymentReturn = window.location.pathname === '/payment/success' || (sessionId?.startsWith('COM-') ?? false);
    if (!isPaymentReturn || !sessionId) return;

    // Wyczyść URL, żeby odświeżenie strony nie powtarzało weryfikacji
    window.history.replaceState({}, '', '/');

    const token = getAccessToken();
    if (!token) {
      setState('pending');
      return;
    }

    setState('checking');
    fetch(`${API_BASE_URL}/payments/verify?session_id=${encodeURIComponent(sessionId)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => {
        if (data.status === 'active') setState('success');
        else if (data.status === 'pending') setState('pending');
        else setState('failed');
      })
      .catch(() => setState('pending'));
  }, []);

  if (!state) return null;

  // Płaska belka pod górnym paskiem: kolor = stan. Potwierdzenie to zielona IKONA
  // (zieleń nigdy nie jest tłem), oczekiwanie i odmowa — żółć „sprawdź”
  const config = {
    checking: {
      icon: <RefreshCw size={18} className="shrink-0 animate-spin text-tv-muted" aria-hidden />,
      text: 'Sprawdzamy status Twojej płatności…',
      cls: 'border-t-2 border-tv-blue bg-tv-panel text-tv-paper',
    },
    success: {
      icon: <CheckCircle size={18} className="shrink-0 text-tv-green" aria-hidden />,
      text: 'Płatność potwierdzona — Twój plan jest aktywny. Dziękujemy!',
      cls: 'border-t-2 border-tv-blue bg-tv-panel text-tv-paper',
    },
    pending: {
      icon: <Clock size={18} className="shrink-0" aria-hidden />,
      text: 'Płatność jest przetwarzana. Dostęp włączy się automatycznie po potwierdzeniu z Przelewy24 (zwykle do kilku minut) — odśwież stronę za chwilę.',
      cls: 'bg-tv-yellow text-tv-ink',
    },
    failed: {
      icon: <XCircle size={18} className="shrink-0" aria-hidden />,
      text: 'Płatność nie została potwierdzona. Jeśli środki zostały pobrane, napisz na biuro@lumargo.pl.',
      cls: 'bg-tv-yellow text-tv-ink',
    },
  }[state];

  const onYellow = state === 'pending' || state === 'failed';

  return (
    <div role="status" className={`fixed left-1/2 top-16 z-[100] flex w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 items-center gap-3 border border-tv-seam py-1 pl-4 pr-1 ${config.cls}`}>
      {config.icon}
      <p className="flex-1 py-2 text-[15px] leading-snug">{config.text}</p>
      {state === 'pending' && (
        <button
          onClick={() => window.location.reload()}
          className="font-cond min-h-[44px] whitespace-nowrap px-2 text-[15px] font-extrabold uppercase tracking-wide underline underline-offset-4 hover:no-underline"
        >
          Odśwież
        </button>
      )}
      <button
        onClick={() => setState(null)}
        aria-label="Zamknij"
        className={`flex h-11 w-11 shrink-0 items-center justify-center transition-colors ${onYellow ? 'hover:bg-[#ffe27a]' : 'text-tv-muted hover:bg-tv-panel2 hover:text-white'}`}
      >
        <X size={18} aria-hidden />
      </button>
    </div>
  );
};

export default PaymentReturnBanner;
