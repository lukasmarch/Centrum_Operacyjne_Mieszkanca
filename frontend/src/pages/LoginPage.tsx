/**
 * Login Page
 */

import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Notice, PageHead } from '../../components/simple/tv';

// Formularz w języku „Paska informacyjnego”: pole 52 px z tekstem 16 px (iOS nie
// powiększa strony przy fokusie), kąty proste, fokus = obrys w kolorze papieru
const LABEL = 'mb-1.5 block text-[15px] font-semibold text-tv-paper';
const INPUT =
  'min-h-[52px] w-full border-2 border-tv-seam bg-tv-ink px-4 text-[16px] text-white outline-none transition-colors placeholder:text-tv-muted focus:border-tv-paper disabled:opacity-60';
const PRIMARY =
  'font-cond min-h-[52px] w-full bg-tv-blue px-4 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-not-allowed disabled:opacity-50';
const LINK = 'font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline';

interface LoginPageProps {
  onNavigate: (page: 'register' | 'dashboard' | 'terms' | 'privacy' | 'reset-password') => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onNavigate }) => {
  const { login, error, clearError } = useAuth();
  // Stan wysyłki lokalnie — globalny `isLoading` odmontowywał formularz (F-036)
  const [isLoading, setIsLoading] = useState(false);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    if (!email || !password) {
      setLocalError('Wypełnij wszystkie pola');
      return;
    }

    setIsLoading(true);
    try {
      await login({ email, password });
      onNavigate('dashboard');
    } catch {
      // Komunikat trzyma AuthContext (`error`), pola zostają wypełnione
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-[70vh] items-center justify-center py-8">
      <div className="w-full max-w-md space-y-5">
        <PageHead title="Witaj ponownie!" sub="Zaloguj się do Centrum Operacyjnego" />

        <div className="border-t-2 border-tv-blue bg-tv-panel p-5 sm:p-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            {(error || localError) && (
              <Notice tone="warn" role="alert">{error || localError}</Notice>
            )}

            <div>
              <label htmlFor="login-email" className={LABEL}>Email</label>
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="twoj@email.pl"
                className={INPUT}
                disabled={isLoading}
              />
            </div>

            <div>
              <label htmlFor="login-password" className={LABEL}>Hasło</label>
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={INPUT}
                disabled={isLoading}
              />
              {/* Do 11.10.2026 przycisk nie robił nic — zapomniane hasło = utracone konto */}
              <button
                type="button"
                onClick={() => onNavigate('reset-password')}
                className={`${LINK} mt-1 min-h-[44px]`}
              >
                Nie pamiętasz hasła?
              </button>
            </div>

            <button type="submit" disabled={isLoading} className={PRIMARY}>
              {isLoading ? 'Logowanie…' : 'Zaloguj się'}
            </button>
          </form>

          <p className="mt-5 flex flex-wrap items-center gap-x-2 border-t border-tv-seam pt-4 text-[15px] text-tv-muted">
            Nie masz jeszcze konta?
            <button onClick={() => onNavigate('register')} className={`${LINK} min-h-[44px]`}>
              Zarejestruj się
            </button>
          </p>
        </div>

        <p className="text-[14px] leading-relaxed text-tv-muted">
          Logując się, akceptujesz{' '}
          <button onClick={() => onNavigate('terms')} className={LINK}>
            Regulamin
          </button>{' '}
          i{' '}
          <button onClick={() => onNavigate('privacy')} className={LINK}>
            Politykę prywatności
          </button>
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
