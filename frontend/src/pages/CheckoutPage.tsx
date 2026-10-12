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
import { Notice, PageHead, Tag } from '../../components/simple/tv';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const LINK = 'font-bold text-tv-bluesoft underline underline-offset-2 transition-colors hover:text-white';

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
    <div className="max-w-3xl space-y-6">
      <button
        onClick={() => onNavigate('premium')}
        className="inline-flex min-h-[44px] items-center gap-1.5 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden /> Wróć do cennika
      </button>

      <PageHead
        title="Podsumowanie zamówienia"
        sub="Sprawdź, co zamawiasz, i potwierdź — zapłacisz przez Przelewy24."
      />

      {/* Zamówienie — plakietka jest nagłówkiem, pod nią panel z chabrową krawędzią */}
      <section>
        <Tag as="h2">Zamówienie</Tag>
        <div className="border-t-2 border-tv-blue bg-tv-panel p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-tv-seam pb-4">
            <div className="min-w-0">
              <p className="font-cond text-[24px] font-extrabold leading-tight text-white">{plan.name}</p>
              <p className="mt-0.5 text-[14px] text-tv-muted">Okres rozliczeniowy: {PERIOD_LABEL[frequency]}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className="font-cond tabular text-[34px] font-extrabold leading-none text-white">{priceLabel} zł</p>
              <p className="mt-1 text-[13px] text-tv-muted">{frequency === 'monthly' ? 'za miesiąc' : 'za rok'} · brutto</p>
            </div>
          </div>

          <ul className="grid grid-cols-1 gap-2 pt-4 text-[14px] text-[#d7dbe8] sm:grid-cols-2">
            {plan.features.map((f) => (
              <li key={f.text} className="flex items-start gap-2">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-tv-bluesoft" aria-hidden />
                <span>{f.text}</span>
              </li>
            ))}
          </ul>

          <div className="mt-6 flex items-baseline justify-between gap-4 border-t border-tv-seam pt-4">
            <span className="text-[15px] text-tv-paper">Do zapłaty dziś</span>
            <span className="font-cond tabular text-[26px] font-extrabold text-white">{priceLabel} zł</span>
          </div>
        </div>
      </section>

      <div className="space-y-4">
        {/* Akceptacja regulaminu — zamówienie z obowiązkiem zapłaty */}
        <label className="flex min-h-[44px] cursor-pointer items-start gap-3 border border-tv-seam bg-tv-panel px-4 py-3">
          <span className="relative inline-flex h-6 w-6 shrink-0">
            <input
              type="checkbox"
              checked={acceptTerms}
              onChange={(e) => setAcceptTerms(e.target.checked)}
              className="peer h-6 w-6 cursor-pointer appearance-none border-2 border-tv-muted bg-tv-ink transition-colors checked:border-tv-blue checked:bg-tv-blue focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tv-yellow"
            />
            <Check size={16} strokeWidth={3} aria-hidden className="pointer-events-none absolute inset-0 m-auto hidden text-white peer-checked:block" />
          </span>
          <span className="text-[15px] leading-relaxed text-[#d7dbe8]">
            Akceptuję{' '}
            <button type="button" onClick={() => onNavigate('terms')} className={LINK}>
              Regulamin
            </button>{' '}
            i składam zamówienie z obowiązkiem zapłaty. Zasady przetwarzania danych opisuje{' '}
            <button type="button" onClick={() => onNavigate('privacy')} className={LINK}>
              Polityka prywatności
            </button>.
          </span>
        </label>

        {!isAuthenticated && (
          <p className="text-[15px] leading-snug text-tv-muted">
            Kolejny krok: założenie konta — dostęp do planu jest przypisany do konta w serwisie.
            Zaraz po nim przejdziesz do płatności.
          </p>
        )}

        {error && <Notice tone="warn" role="alert">{error}</Notice>}
        {notice && <Notice tone="warn" role="status">{notice}</Notice>}

        <button
          onClick={handleOrder}
          disabled={busy}
          className="font-cond tabular min-h-[56px] w-full bg-tv-blue px-4 text-[18px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-wait disabled:opacity-60"
        >
          {busy ? 'Łączenie z Przelewy24…' : isAuthenticated ? `Zamawiam i płacę ${priceLabel} zł` : 'Przejdź do płatności'}
        </button>

        <p className="flex items-center justify-center gap-2 text-center text-[13px] text-tv-muted">
          <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden /> Płatność obsługuje PayPro S.A. (Przelewy24) — BLIK, karta, przelew online
        </p>
      </div>

      {/* Dane sprzedawcy i uprawnienia kupującego */}
      <div className="grid grid-cols-1 gap-px bg-tv-seam md:grid-cols-2">
        <section className="bg-tv-panel p-5">
          <h3 className="font-cond mb-2 text-[18px] font-extrabold text-white">Sprzedawca</h3>
          <p className="text-[14px] leading-relaxed text-[#d7dbe8]">
            Studio Kamienia Naturalnego Lu-Mar-Go Łukasz Marchlewicz<br />
            Żabiny 96, 13-220 Rybno<br />
            NIP: <span className="tabular">571-156-78-15</span><br />
            <a href="tel:+48501081723" className="tabular text-tv-bluesoft underline-offset-2 hover:text-white hover:underline">+48 501 081 723</a><br />
            <a href="mailto:biuro@lumargo.pl" className="text-tv-bluesoft underline-offset-2 hover:text-white hover:underline">biuro@lumargo.pl</a>
          </p>
        </section>
        <section className="bg-tv-panel p-5">
          <h3 className="font-cond mb-2 text-[18px] font-extrabold text-white">Rezygnacja i odstąpienie</h3>
          <p className="text-[14px] leading-relaxed text-[#d7dbe8]">
            Płatność jest jednorazowa — subskrypcja nie odnawia się automatycznie i wygasa po opłaconym okresie.
            Konsumentowi przysługuje prawo odstąpienia od umowy w terminie 14 dni; wzór oświadczenia
            znajduje się w{' '}
            <button type="button" onClick={() => onNavigate('terms')} className={LINK}>
              Regulaminie
            </button>.
          </p>
        </section>
      </div>
    </div>
  );
};

export default CheckoutPage;
