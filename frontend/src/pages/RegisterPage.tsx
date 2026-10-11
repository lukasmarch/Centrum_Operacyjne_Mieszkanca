/**
 * Register Page
 */

import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { track } from '../services/analytics';
import { AVAILABLE_LOCATIONS } from '../../types';
import { ApiError } from '../services/apiError';

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
    location: 'Rybno',
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
    `w-full px-4 py-3 rounded-xl border ${fieldErrors[name] ? 'border-red-500' : 'border-gray-700'} bg-gray-900 text-white placeholder:text-gray-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all`;

  const fieldError = (name: string) =>
    fieldErrors[name] ? (
      <p id={`${name}-error`} role="alert" className="mt-1 text-sm text-red-400">{fieldErrors[name]}</p>
    ) : null;

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-8">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center font-bold text-3xl text-white mx-auto mb-4">
            D
          </div>
          <h1 className="text-3xl font-black mb-2 text-white">Dołącz do nas!</h1>
          <p className="text-neutral-500">Stwórz konto w Centrum Operacyjnym</p>
        </div>

        {/* Form */}
        <div className="bg-gray-950 rounded-3xl p-8 shadow-sm border border-gray-800/50">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Error message */}
            {/* Komunikat ogólny — chyba że to ten sam, który stoi już przy polu
                („Ten adres ma już konto” przy e-mailu), wtedy raz wystarczy */}
            {(error || localError) && !Object.values(fieldErrors).includes(error || localError) && (
              <div role="alert" className="p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">
                {error || localError}
              </div>
            )}

            {/* Full name */}
            <div>
              <label className="block text-sm font-semibold text-neutral-300 mb-2">
                Imię i nazwisko *
              </label>
              <input
                type="text"
                name="full_name"
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

            {/* Email */}
            <div>
              <label className="block text-sm font-semibold text-neutral-300 mb-2">
                Email *
              </label>
              <input
                type="email"
                name="email"
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

            {/* Location */}
            <div>
              <label className="block text-sm font-semibold text-neutral-300 mb-2">
                Miejscowość
              </label>
              <select
                name="location"
                value={formData.location}
                onChange={handleChange}
                className="w-full px-4 py-3 rounded-xl border border-gray-700 bg-gray-900 text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                disabled={isLoading}
              >
                {AVAILABLE_LOCATIONS.map((loc) => (
                  <option key={loc} value={loc}>
                    {loc}
                  </option>
                ))}
              </select>
              <p className="text-xs text-neutral-400 mt-1">
                Wybierz swoją miejscowość, aby otrzymywać spersonalizowane informacje
              </p>
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-semibold text-neutral-300 mb-2">
                Hasło *
              </label>
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="••••••••"
                className={fieldClass('password')}
                aria-invalid={!!fieldErrors.password}
                aria-describedby={fieldErrors.password ? 'password-error' : undefined}
                disabled={isLoading}
              />
              {fieldError('password')}
              <p className="text-xs text-neutral-400 mt-1">
                Min. 8 znaków, wielka litera i cyfra
              </p>
            </div>

            {/* Confirm password */}
            <div>
              <label className="block text-sm font-semibold text-neutral-300 mb-2">
                Potwierdź hasło *
              </label>
              <input
                type="password"
                name="confirmPassword"
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

            {/* Zgody RODO */}
            <div className="space-y-3 pt-1">
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={consentTerms}
                  onChange={(e) => setConsentTerms(e.target.checked)}
                  disabled={isLoading}
                  className="mt-0.5 accent-blue-500 shrink-0"
                />
                <span className="text-xs text-neutral-400 leading-relaxed">
                  Akceptuję{' '}
                  <button type="button" onClick={() => onNavigate('terms')} className="text-blue-400 hover:underline">
                    Regulamin
                  </button>{' '}
                  i zapoznałem/am się z{' '}
                  <button type="button" onClick={() => onNavigate('privacy')} className="text-blue-400 hover:underline">
                    Polityką prywatności
                  </button>{' '}
                  <span className="text-red-400">*</span>
                </span>
              </label>
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={consentMarketing}
                  onChange={(e) => setConsentMarketing(e.target.checked)}
                  disabled={isLoading}
                  className="mt-0.5 accent-blue-500 shrink-0"
                />
                <span className="text-xs text-neutral-400 leading-relaxed">
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
              <div className="mt-3 rounded-xl border border-emerald-500/25 bg-emerald-500/5 px-4 py-3">
                <p className="text-xs font-bold text-emerald-300">
                  Plan Premium bez opłat — na czas pełnienia funkcji
                </p>
                <p className="mt-1 text-xs text-neutral-400 leading-relaxed">
                  Po założeniu konta od razu przejdziesz do panelu sołectwa,
                  a na maila przyjdzie instrukcja dodawania ogłoszeń.
                </p>
              </div>
            ) : (
              <div className="mt-3 rounded-xl border border-amber-500/25 bg-amber-500/5 px-4 py-3">
                <p className="text-xs font-bold text-amber-300">
                  30 dni planu Premium — bez karty płatniczej
                </p>
                <p className="mt-1 text-xs text-neutral-400 leading-relaxed">
                  Poranny briefing na mail, asystent AI bez limitu i powiadomienia o awariach.
                  Potem konto przechodzi na darmowy plan Dla Każdego — nic nie pobieramy
                  automatycznie i uprzedzimy Cię mailem tydzień wcześniej.
                </p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading || !consentTerms}
              className="w-full py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Tworzenie konta...
                </span>
              ) : (
                'Zarejestruj się'
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-800/50"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-gray-950 text-neutral-400">lub</span>
            </div>
          </div>

          {/* Login link */}
          <p className="text-center text-neutral-400">
            Masz już konto?{' '}
            <button
              onClick={() => onNavigate('login')}
              className="text-blue-600 font-bold hover:text-blue-700"
            >
              Zaloguj się
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
