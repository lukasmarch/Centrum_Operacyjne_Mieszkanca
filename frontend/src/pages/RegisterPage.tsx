/**
 * Register Page
 */

import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { track } from '../services/analytics';
import { AVAILABLE_LOCATIONS } from '../../types';
import { guestVillage } from '../hooks/useMyVillage';
import { ApiError } from '../services/apiError';
import { Check } from 'lucide-react';
import { Notice, PageHead } from '../../components/simple/tv';

// Formularz w języku „Paska informacyjnego” — te same miary co logowanie:
// pole 52 px, tekst 16 px (iOS nie powiększa przy fokusie), kąty proste.
// Obramowanie dokłada `fieldClass` (szew albo żółć przy błędzie)
const LABEL = 'mb-1.5 block text-[15px] font-semibold text-tv-paper';
const INPUT =
  'min-h-[52px] w-full border-2 bg-tv-ink px-4 text-[16px] text-white outline-none transition-colors placeholder:text-tv-muted focus:border-tv-paper disabled:opacity-60';
const HINT = 'mt-1.5 text-[13px] leading-snug text-tv-muted';
const PRIMARY =
  'font-cond min-h-[52px] w-full bg-tv-blue px-4 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-not-allowed disabled:opacity-50';
const LINK = 'font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline';

/** Kwadratowe pole zgody 24 px — natywny checkbox bez wyglądu, znaczek z lucide */
const SquareCheck: React.FC<{ checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }> = ({
  checked, onChange, disabled,
}) => (
  <span className="relative mt-[-1px] inline-flex h-6 w-6 shrink-0">
    <input
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      disabled={disabled}
      className="peer h-6 w-6 cursor-pointer appearance-none border-2 border-tv-muted bg-tv-ink transition-colors checked:border-tv-blue checked:bg-tv-blue focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tv-yellow disabled:opacity-60"
    />
    <Check size={16} strokeWidth={3} aria-hidden className="pointer-events-none absolute inset-0 m-auto hidden text-white peer-checked:block" />
  </span>
);

interface RegisterPageProps {
  onNavigate: (page: 'login' | 'dashboard' | 'terms' | 'privacy') => void;
  /** Kod z zaproszenia (strona `/zaproszenie`) — konto powstaje od razu z rolą */
  inviteToken?: string;
  /** Po udanej rejestracji z zaproszeniem — zamiast powrotu na stronę główną */
  onRegistered?: () => void;
}

const RegisterPage: React.FC<RegisterPageProps> = ({ onNavigate, inviteToken, onRegistered }) => {
  const { register, error, clearError } = useAuth();
  // Stan wysyłki lokalnie: globalny `isLoading` z AuthContext steruje ekranem
  // ładowania całej aplikacji, więc formularz znikał i wracał pusty (F-036)
  const [isLoading, setIsLoading] = useState(false);

  // Górny stopień lejka: ilu ludzi w ogóle otworzyło formularz. Bez tego
  // „zero rejestracji" nie odróżnia się od „nikt tu nie doszedł".
  useEffect(() => { track('register_open', { section: 'register' }); }, []);

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    // Wieś wybrana na pulpicie jako gość przechodzi do konta — bez pytania drugi raz.
    // „Rybno” bez rejonu nie jest pozycją listy (R1/R2), więc wtedy zostaje stan dawny
    location: (() => {
      const picked = guestVillage();
      return picked && (AVAILABLE_LOCATIONS as readonly string[]).includes(picked) ? picked : 'Rybno';
    })(),
  });
  const [consentTerms, setConsentTerms] = useState(false);
  const [consentMarketing, setConsentMarketing] = useState(false);
  const [localError, setLocalError] = useState('');
  // Komunikat PRZY polu — ogólne „Popraw dane” nad formularzem nie mówi, które
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Poprawiane pole traci swój komunikat od razu, reszta zostaje
    setFieldErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const validatePassword = (password: string): string | null => {
    if (password.length < 8) {
      return 'Hasło musi mieć minimum 8 znaków';
    }
    if (!/[A-Z]/.test(password)) {
      return 'Hasło musi zawierać wielką literę';
    }
    if (!/[0-9]/.test(password)) {
      return 'Hasło musi zawierać cyfrę';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError('');
    setFieldErrors({});
    clearError();

    const errors: Record<string, string> = {};
    if (formData.full_name.trim().length < 2) errors.full_name = 'Podaj imię i nazwisko (min. 2 znaki).';
    if (!formData.email.trim()) errors.email = 'Podaj adres e-mail.';
    const passwordError = validatePassword(formData.password);
    if (passwordError) errors.password = passwordError;
    else if (formData.password !== formData.confirmPassword) errors.confirmPassword = 'Hasła nie są identyczne.';
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      setLocalError('Popraw zaznaczone pola.');
      return;
    }

    if (!consentTerms) {
      setLocalError('Rejestracja wymaga akceptacji Regulaminu i Polityki prywatności');
      return;
    }

    setIsLoading(true);
    try {
      await register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        location: formData.location,
        consent_terms: consentTerms,
        consent_marketing: consentMarketing,
        ...(inviteToken ? { invite_token: inviteToken } : {}),
      });
      // Mail powitalny obiecuje alerty o awariach i przypomnienie o wywozie — oba
      // jadą wyłącznie pushem, a ten wymaga zgody w przeglądarce. Do 21.08.2026
      // prośbę o nią widział tylko ten, kto trafił na feed w dniu realnej awarii,
      // więc świeże konto zostawało z obietnicą bez włącznika. Znacznik czyta
      // Dashboard (AlertPushPrompt).
      try {
        localStorage.setItem('rl_registered_at', String(Date.now()));
      } catch {
        // tryb prywatny bez localStorage — baner po prostu się nie pokaże
      }
      if (onRegistered) onRegistered();
      else onNavigate('dashboard');
    } catch (err) {
      // Ogólny komunikat trzyma AuthContext (`error`); tu tylko przypięcie do pól
      if (err instanceof ApiError) setFieldErrors(err.fields);
    } finally {
      setIsLoading(false);
    }
  };

  const fieldClass = (name: string) =>
    `${INPUT} ${fieldErrors[name] ? 'border-tv-yellow' : 'border-tv-seam'}`;

  const fieldError = (name: string) =>
    fieldErrors[name] ? (
      <p id={`${name}-error`} role="alert" className="mt-1.5 text-[14px] font-semibold text-tv-yellow">{fieldErrors[name]}</p>
    ) : null;

  return (
    <div className="flex min-h-[70vh] items-center justify-center py-8">
      <div className="w-full max-w-md space-y-5">
        <PageHead title="Dołącz do nas!" sub="Stwórz konto w Centrum Operacyjnym" />

        <div className="border-t-2 border-tv-blue bg-tv-panel p-5 sm:p-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Komunikat ogólny — chyba że to ten sam, który stoi już przy polu
                („Ten adres ma już konto” przy e-mailu), wtedy raz wystarczy */}
            {(error || localError) && !Object.values(fieldErrors).includes(error || localError) && (
              <Notice tone="warn" role="alert">{error || localError}</Notice>
            )}

            <div>
              <label htmlFor="reg-full_name" className={LABEL}>
                Imię i nazwisko *
              </label>
              <input
                id="reg-full_name"
                type="text"
                name="full_name"
                autoComplete="name"
                value={formData.full_name}
                onChange={handleChange}
                placeholder="Jan Kowalski"
                className={fieldClass('full_name')}
                aria-invalid={!!fieldErrors.full_name}
                aria-describedby={fieldErrors.full_name ? 'full_name-error' : undefined}
                disabled={isLoading}
              />
              {fieldError('full_name')}
            </div>

            <div>
              <label htmlFor="reg-email" className={LABEL}>
                Email *
              </label>
              <input
                id="reg-email"
                type="email"
                name="email"
                autoComplete="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="twoj@email.pl"
                className={fieldClass('email')}
                aria-invalid={!!fieldErrors.email}
                aria-describedby={fieldErrors.email ? 'email-error' : undefined}
                disabled={isLoading}
              />
              {fieldError('email')}
            </div>

            <div>
              <label htmlFor="reg-location" className={LABEL}>
                Miejscowość
              </label>
              <select
                id="reg-location"
                name="location"
                value={formData.location}
                onChange={handleChange}
                className={`${INPUT} border-tv-seam`}
                disabled={isLoading}
              >
                {AVAILABLE_LOCATIONS.map((loc) => (
                  <option key={loc} value={loc}>
                    {loc}
                  </option>
                ))}
              </select>
              <p className={HINT}>
                Wybierz swoją miejscowość, aby otrzymywać spersonalizowane informacje
              </p>
            </div>

            <div>
              <label htmlFor="reg-password" className={LABEL}>
                Hasło *
              </label>
              <input
                id="reg-password"
                type="password"
                name="password"
                autoComplete="new-password"
                value={formData.password}
                onChange={handleChange}
                placeholder="••••••••"
                className={fieldClass('password')}
                aria-invalid={!!fieldErrors.password}
                aria-describedby={fieldErrors.password ? 'password-error' : undefined}
                disabled={isLoading}
              />
              {fieldError('password')}
              <p className={HINT}>
                Min. 8 znaków, wielka litera i cyfra
              </p>
            </div>

            <div>
              <label htmlFor="reg-confirmPassword" className={LABEL}>
                Potwierdź hasło *
              </label>
              <input
                id="reg-confirmPassword"
                type="password"
                name="confirmPassword"
                autoComplete="new-password"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="••••••••"
                className={fieldClass('confirmPassword')}
                aria-invalid={!!fieldErrors.confirmPassword}
                aria-describedby={fieldErrors.confirmPassword ? 'confirmPassword-error' : undefined}
                disabled={isLoading}
              />
              {fieldError('confirmPassword')}
            </div>

            {/* Zgody RODO — treść bez zmian; pole kwadratowe 24 px w wierszu ≥ 44 px */}
            <div className="space-y-1 border-t border-tv-seam pt-3">
              <label className="flex min-h-[44px] cursor-pointer items-start gap-3 py-2.5">
                <SquareCheck
                  checked={consentTerms}
                  onChange={setConsentTerms}
                  disabled={isLoading}
                />
                <span className="text-[14px] leading-relaxed text-[#d7dbe8]">
                  Akceptuję{' '}
                  <button type="button" onClick={() => onNavigate('terms')} className={LINK}>
                    Regulamin
                  </button>{' '}
                  i zapoznałem/am się z{' '}
                  <button type="button" onClick={() => onNavigate('privacy')} className={LINK}>
                    Polityką prywatności
                  </button>{' '}
                  <span className="text-tv-paper">*</span>
                </span>
              </label>
              <label className="flex min-h-[44px] cursor-pointer items-start gap-3 py-2.5">
                <SquareCheck
                  checked={consentMarketing}
                  onChange={setConsentMarketing}
                  disabled={isLoading}
                />
                <span className="text-[14px] leading-relaxed text-[#d7dbe8]">
                  Chcę dostawać informacje o nowościach w serwisie i oferty lokalnych firm
                  (opcjonalne, zgodę można cofnąć w każdej chwili)
                </span>
              </label>
            </div>

            {/* Co daje konto — mówimy to PRZED rejestracją.
                Do 20.08.2026 informacja o 30 dniach Premium istniała wyłącznie
                w regulaminie: użytkownik dostawał pełny dostęp, nie wiedział,
                że jest ograniczony, i nie miał powodu niczego kupować. */}
            {/* Konto z zaproszenia (sołtys) dostaje Premium BEZ terminu — obietnica
                30 dni byłaby tu nieprawdą (backend: `roles.grant_role`) */}
            {inviteToken ? (
              <div className="border border-tv-seam bg-tv-ink px-4 py-3">
                <p className="font-cond text-[16px] font-extrabold leading-snug text-white">
                  Plan Premium bez opłat — na czas pełnienia funkcji
                </p>
                <p className="mt-1 text-[14px] leading-relaxed text-[#d7dbe8]">
                  Po założeniu konta od razu przejdziesz do panelu sołectwa,
                  a na maila przyjdzie instrukcja dodawania ogłoszeń.
                </p>
              </div>
            ) : (
              <div className="border border-tv-seam bg-tv-ink px-4 py-3">
                <p className="font-cond text-[16px] font-extrabold leading-snug text-white">
                  30 dni planu Premium — bez karty płatniczej
                </p>
                <p className="mt-1 text-[14px] leading-relaxed text-[#d7dbe8]">
                  Poranny briefing na mail, asystent AI bez limitu i powiadomienia o awariach.
                  Potem konto przechodzi na darmowy plan Dla Każdego — nic nie pobieramy
                  automatycznie i uprzedzimy Cię mailem tydzień wcześniej.
                </p>
              </div>
            )}

            <button type="submit" disabled={isLoading || !consentTerms} className={PRIMARY}>
              {isLoading ? 'Tworzenie konta…' : 'Zarejestruj się'}
            </button>
          </form>

          <p className="mt-5 flex flex-wrap items-center gap-x-2 border-t border-tv-seam pt-4 text-[15px] text-tv-muted">
            Masz już konto?
            <button onClick={() => onNavigate('login')} className={`${LINK} min-h-[44px]`}>
              Zaloguj się
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
