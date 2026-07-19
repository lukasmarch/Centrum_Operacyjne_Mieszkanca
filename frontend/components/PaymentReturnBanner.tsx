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

  const config = {
    checking: {
      icon: <RefreshCw size={18} className="animate-spin text-blue-400" />,
      text: 'Sprawdzamy status Twojej płatności…',
      cls: 'border-blue-500/30 bg-blue-950/90',
    },
    success: {
      icon: <CheckCircle size={18} className="text-emerald-400" />,
      text: 'Płatność potwierdzona — Twój plan jest aktywny. Dziękujemy!',
      cls: 'border-emerald-500/30 bg-emerald-950/90',
    },
    pending: {
      icon: <Clock size={18} className="text-amber-400" />,
      text: 'Płatność jest przetwarzana. Dostęp włączy się automatycznie po potwierdzeniu z Przelewy24 (zwykle do kilku minut) — odśwież stronę za chwilę.',
      cls: 'border-amber-500/30 bg-amber-950/90',
    },
    failed: {
      icon: <XCircle size={18} className="text-red-400" />,
      text: 'Płatność nie została potwierdzona. Jeśli środki zostały pobrane, napisz na biuro@lumargo.pl.',
      cls: 'border-red-500/30 bg-red-950/90',
    },
  }[state];

  return (
    <div className={`fixed top-16 left-1/2 -translate-x-1/2 z-[100] w-[calc(100%-2rem)] max-w-xl rounded-2xl border ${config.cls} backdrop-blur px-4 py-3 flex items-center gap-3 shadow-xl`}>
      {config.icon}
      <p className="text-sm text-neutral-200 flex-1">{config.text}</p>
      {state === 'pending' && (
        <button
          onClick={() => window.location.reload()}
          className="text-xs font-semibold text-amber-300 hover:text-amber-200 whitespace-nowrap"
        >
          Odśwież
        </button>
      )}
      <button onClick={() => setState(null)} className="text-neutral-500 hover:text-white">
        <X size={16} />
      </button>
    </div>
  );
};

export default PaymentReturnBanner;
