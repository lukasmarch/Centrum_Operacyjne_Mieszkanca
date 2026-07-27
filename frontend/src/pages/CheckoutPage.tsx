/**
 * Podsumowanie zamówienia — publiczny krok między cennikiem a płatnością.
 *
 * Dostępny bez konta (pod adresem /zamowienie?plan=premium&okres=monthly), bo kupujący
 * musi poznać cenę, warunki i kolejne kroki przed rejestracją. Konto zakłada się
 * dopiero po zaakceptowaniu zamówienia — dostęp jest przypisany do konta w serwisie.
 */
import React, { useState, useEffect } from 'react';
import { Check, ArrowLeft, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { AppSection } from '../../types';
import { PLANS, Frequency } from '../../components/PricingCards';
import { getAccessToken } from '../services/authApi';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface CheckoutPageProps {
  tierKey: string;
  frequency: Frequency;
  onNavigate: (section: AppSection) => void;
}

// Subskrypcja nie odnawia się automatycznie — płatność jest jednorazowa, z góry za okres
const PERIOD_LABEL: Record<Frequency, string> = {
  monthly: 'miesięczny — jednorazowa płatność z góry za 31 dni',
  yearly: 'roczny — jednorazowa płatność z góry za 12 miesięcy',
};

const CheckoutPage: React.FC<CheckoutPageProps> = ({ tierKey, frequency, onNavigate }) => {
  const { isAuthenticated } = useAuth();
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Wejście z cennika następuje z połowy długiej strony — zamówienie zaczynamy od góry
  useEffect(() => { window.scrollTo({ top: 0 }); }, []);

  const plan = PLANS.find((p) => p.tierKey === tierKey) ?? PLANS[1];
  const price = plan.price[frequency];
  const priceLabel = price.toFixed(2).replace('.', ',');

  const handleOrder = async () => {
    setError(null);
    setNotice(null);

    if (!acceptTerms) {
      setError('Zaznacz akceptację Regulaminu — bez tego nie możemy przyjąć zamówienia.');
      return;
    }

    // Dostęp jest przypisany do konta, więc niezalogowany kupujący najpierw je zakłada.
    // Wybór planu zostaje w adresie, żeby po rejestracji wrócić do tego samego zamówienia.
    if (!isAuthenticated) {
      onNavigate('register');
      return;
    }

    setBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/payments/create-transaction`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({ tier: plan.tierKey, period: frequency, accept_terms: true }),
      });

      if (res.status === 503) {
        // Bramka jeszcze nieaktywna — zamiast surowego błędu podajemy drogę do zakupu
        setNotice(
          'Płatności online są w tej chwili uruchamiane u operatora płatności. ' +
          'Napisz na biuro@lumargo.pl lub zadzwoń pod +48 501 081 723 — przyjmiemy zamówienie, ' +
          'aktywujemy plan i wystawimy fakturę.'
        );
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || 'Nie udało się rozpocząć płatności. Spróbuj ponownie za chwilę.');
        return;
      }

      const data = await res.json();
      window.location.href = data.redirect_url;
    } catch {
      setError('Brak połączenia z serwisem płatności. Sprawdź internet i spróbuj ponownie.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-10">
      <button
        onClick={() => onNavigate('premium')}
        className="flex items-center gap-2 text-sm text-neutral-400 hover:text-white transition-colors mb-6"
      >
        <ArrowLeft className="w-4 h-4" /> Wróć do cennika
      </button>

      <h2 className="text-3xl font-black mb-2">Podsumowanie zamówienia</h2>
      <p className="text-neutral-500 mb-8">Sprawdź, co zamawiasz, i potwierdź — zapłacisz przez Przelewy24.</p>

      {/* Zamówienie */}
      <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6 mb-6">
        <div className="flex items-start justify-between gap-4 pb-4 border-b border-white/10">
          <div>
            <p className="text-xl font-bold">{plan.name}</p>
            <p className="text-sm text-neutral-500">Okres rozliczeniowy: {PERIOD_LABEL[frequency]}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-3xl font-black">{priceLabel} zł</p>
            <p className="text-xs text-neutral-500">{frequency === 'monthly' ? 'za miesiąc' : 'za rok'} · brutto</p>
          </div>
        </div>

        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-4 text-sm text-neutral-400">
          {plan.features.map((f) => (
            <li key={f.text} className="flex items-start gap-2">
              <Check className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />
              <span>{f.text}</span>
            </li>
          ))}
        </ul>

        <div className="flex items-center justify-between gap-4 mt-6 pt-4 border-t border-white/10">
          <span className="text-sm text-neutral-400">Do zapłaty dziś</span>
          <span className="text-xl font-bold">{priceLabel} zł</span>
        </div>
      </div>

      {/* Akceptacja regulaminu — zamówienie z obowiązkiem zapłaty */}
      <label className="flex items-start gap-3 p-4 bg-white/[0.03] border border-white/10 rounded-xl mb-4 cursor-pointer">
        <input
          type="checkbox"
          checked={acceptTerms}
          onChange={(e) => setAcceptTerms(e.target.checked)}
          className="w-5 h-5 rounded accent-blue-600 mt-0.5 shrink-0"
        />
        <span className="text-sm text-neutral-300">
          Akceptuję{' '}
          <button type="button" onClick={() => onNavigate('terms')} className="text-blue-400 hover:text-blue-300 underline underline-offset-2">
            Regulamin
          </button>{' '}
          i składam zamówienie z obowiązkiem zapłaty. Zasady przetwarzania danych opisuje{' '}
          <button type="button" onClick={() => onNavigate('privacy')} className="text-blue-400 hover:text-blue-300 underline underline-offset-2">
            Polityka prywatności
          </button>.
        </span>
      </label>

      {!isAuthenticated && (
        <p className="text-sm text-neutral-500 mb-4 px-1">
          Kolejny krok: założenie konta — dostęp do planu jest przypisany do konta w serwisie.
          Zaraz po nim przejdziesz do płatności.
        </p>
      )}

      {error && (
        <div className="mb-4 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-sm text-red-300">{error}</div>
      )}
      {notice && (
        <div className="mb-4 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-sm text-amber-200">{notice}</div>
      )}

      <button
        onClick={handleOrder}
        disabled={busy}
        className="w-full py-4 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-60 font-bold text-white transition-colors"
      >
        {busy ? 'Łączenie z Przelewy24…' : isAuthenticated ? `Zamawiam i płacę ${priceLabel} zł` : 'Przejdź do płatności'}
      </button>

      <p className="flex items-center justify-center gap-2 text-xs text-neutral-500 mt-3">
        <ShieldCheck className="w-4 h-4" /> Płatność obsługuje PayPro S.A. (Przelewy24) — BLIK, karta, przelew online
      </p>

      {/* Dane sprzedawcy i uprawnienia kupującego */}
      <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-6 text-sm text-neutral-400">
        <div>
          <h3 className="font-bold text-neutral-300 mb-2">Sprzedawca</h3>
          <p className="leading-relaxed">
            Studio Kamienia Naturalnego Lu-Mar-Go<br />
            Żabiny 96, 13-220 Rybno<br />
            NIP: 571-156-78-15<br />
            <a href="tel:+48501081723" className="hover:text-blue-400 transition-colors">+48 501 081 723</a><br />
            <a href="mailto:biuro@lumargo.pl" className="hover:text-blue-400 transition-colors">biuro@lumargo.pl</a>
          </p>
        </div>
        <div>
          <h3 className="font-bold text-neutral-300 mb-2">Rezygnacja i odstąpienie</h3>
          <p className="leading-relaxed">
            Płatność jest jednorazowa — subskrypcja nie odnawia się automatycznie i wygasa po opłaconym okresie.
            Konsumentowi przysługuje prawo odstąpienia od umowy w terminie 14 dni; wzór oświadczenia
            znajduje się w{' '}
            <button type="button" onClick={() => onNavigate('terms')} className="text-blue-400 hover:text-blue-300 underline underline-offset-2">
              Regulaminie
            </button>.
          </p>
        </div>
      </div>
    </div>
  );
};

export default CheckoutPage;
