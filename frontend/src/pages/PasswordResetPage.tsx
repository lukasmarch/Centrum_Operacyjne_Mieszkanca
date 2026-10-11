/**
 * Nowe hasło — `/nowe-haslo` (audyt 11.10.2026, F-028).
 *
 * Dwa tryby jednej strony:
 *  - bez tokenu: „podaj e-mail” → link na skrzynkę (backend odpowiada tak samo
 *    dla każdego adresu, więc strona też nie mówi, czy konto istnieje);
 *  - z `?token=` z maila: „ustaw nowe hasło” → konto zalogowane od razu.
 *
 * Do 11.10.2026 przycisk „Zapomniałeś hasła?” na stronie logowania nie robił
 * nic, a zapomniane hasło znaczyło utracone konto.
 *
 * ⚠️ Token zdejmujemy z paska adresu zaraz po odczycie: link do ustawienia
 * hasła nie powinien zostawać w historii przeglądarki ani iść dalej w nagłówku
 * Referer, gdy ktoś kliknie z tej strony link zewnętrzny.
 */

import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { forgotPassword } from '../services/authApi';
import { ApiError } from '../services/apiError';

interface PasswordResetPageProps {
  onNavigate: (page: 'login' | 'dashboard') => void;
}

const tokenFromUrl = () => new URLSearchParams(window.location.search).get('token') ?? '';

const inputClass = (invalid: boolean) =>
  `w-full px-4 py-3 rounded-xl bg-gray-900 border ${invalid ? 'border-red-500' : 'border-gray-700/50'} text-neutral-100 placeholder-neutral-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all`;

const validatePassword = (password: string): string | null => {
  if (password.length < 8) return 'Hasło musi mieć minimum 8 znaków.';
  if (!/[A-Z]/.test(password)) return 'Hasło musi zawierać wielką literę.';
  if (!/[0-9]/.test(password)) return 'Hasło musi zawierać cyfrę.';
  return null;
};

const PasswordResetPage: React.FC<PasswordResetPageProps> = ({ onNavigate }) => {
  const { resetPassword } = useAuth();
  const [token] = useState(tokenFromUrl);

  useEffect(() => {
    if (token) window.history.replaceState({}, '', '/nowe-haslo');
  }, [token]);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [fieldError, setFieldError] = useState<{ field: string; message: string } | null>(null);
  const [sentMessage, setSentMessage] = useState('');
  const [linkDead, setLinkDead] = useState(false);

  const requestLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setFieldError(null);
    if (!email.trim()) {
      setFieldError({ field: 'email', message: 'Podaj adres e-mail.' });
      return;
    }
    setSending(true);
    try {
      setSentMessage(await forgotPassword(email.trim()));
    } catch (err) {
      if (err instanceof ApiError && err.fields.email) setFieldError({ field: 'email', message: err.fields.email });
      else setError(err instanceof Error ? err.message : 'Nie udało się wysłać linku.');
    } finally {
      setSending(false);
    }
  };

  const setNewPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setFieldError(null);
    const weak = validatePassword(password);
    if (weak) {
      setFieldError({ field: 'password', message: weak });
      return;
    }
    if (password !== confirm) {
      setFieldError({ field: 'confirm', message: 'Hasła nie są identyczne.' });
      return;
    }
    setSending(true);
    try {
      await resetPassword(token, password);
      onNavigate('dashboard');
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) setLinkDead(true);
      else if (err instanceof ApiError && err.fields.new_password) {
        setFieldError({ field: 'password', message: err.fields.new_password });
      } else setError(err instanceof Error ? err.message : 'Nie udało się ustawić hasła.');
    } finally {
      setSending(false);
    }
  };

  const fieldMessage = (field: string) =>
    fieldError?.field === field ? (
      <p id={`${field}-error`} role="alert" className="mt-1 text-sm text-red-400">{fieldError.message}</p>
    ) : null;

  const submitLabel = token ? 'Ustaw nowe hasło' : 'Wyślij link';

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-8">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-black mb-2 text-neutral-100">
            {token ? 'Ustaw nowe hasło' : 'Nie pamiętasz hasła?'}
          </h1>
          <p className="text-neutral-400">
            {token
              ? 'Po zapisaniu wylogujemy wszystkie inne urządzenia.'
              : 'Podaj adres konta — wyślemy link do ustawienia nowego hasła.'}
          </p>
        </div>

        <div className="bg-gray-950/50 backdrop-blur-xl rounded-3xl p-8 shadow-xl border border-gray-800/50">
          {sentMessage ? (
            <div role="status" className="space-y-4">
              <p className="text-base leading-relaxed text-neutral-200">{sentMessage}</p>
              <p className="text-sm text-neutral-400">
                Nie widzisz maila? Sprawdź folder „Oferty” lub „Spam”.
              </p>
              <button
                type="button"
                onClick={() => onNavigate('login')}
                className="min-h-[44px] text-sm font-semibold text-blue-400 hover:text-blue-300"
              >
                Wróć do logowania
              </button>
            </div>
          ) : linkDead ? (
            <div role="alert" className="space-y-4">
              <p className="text-base leading-relaxed text-neutral-200">
                Ten link wygasł albo został już użyty. Link działa przez godzinę i tylko raz.
              </p>
              <button
                type="button"
                onClick={() => { setLinkDead(false); window.location.assign('/nowe-haslo'); }}
                className="w-full py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-colors"
              >
                Poproś o nowy link
              </button>
            </div>
          ) : (
            <form onSubmit={token ? setNewPassword : requestLink} className="space-y-5" noValidate>
              {error && (
                <div role="alert" className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                  {error}
                </div>
              )}

              {!token ? (
                <div>
                  <label htmlFor="reset-email" className="block text-sm font-semibold text-neutral-300 mb-2">
                    Email
                  </label>
                  <input
                    id="reset-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setFieldError(null); }}
                    placeholder="twoj@email.pl"
                    className={inputClass(fieldError?.field === 'email')}
                    aria-invalid={fieldError?.field === 'email'}
                    aria-describedby={fieldError?.field === 'email' ? 'email-error' : undefined}
                    disabled={sending}
                  />
                  {fieldMessage('email')}
                </div>
              ) : (
                <>
                  <div>
                    <label htmlFor="reset-password" className="block text-sm font-semibold text-neutral-300 mb-2">
                      Nowe hasło
                    </label>
                    <input
                      id="reset-password"
                      type="password"
                      autoComplete="new-password"
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); setFieldError(null); }}
                      placeholder="••••••••"
                      className={inputClass(fieldError?.field === 'password')}
                      aria-invalid={fieldError?.field === 'password'}
                      aria-describedby={fieldError?.field === 'password' ? 'password-error' : undefined}
                      disabled={sending}
                    />
                    {fieldMessage('password')}
                    <p className="text-xs text-neutral-400 mt-1">Min. 8 znaków, wielka litera i cyfra</p>
                  </div>
                  <div>
                    <label htmlFor="reset-confirm" className="block text-sm font-semibold text-neutral-300 mb-2">
                      Powtórz hasło
                    </label>
                    <input
                      id="reset-confirm"
                      type="password"
                      autoComplete="new-password"
                      value={confirm}
                      onChange={(e) => { setConfirm(e.target.value); setFieldError(null); }}
                      placeholder="••••••••"
                      className={inputClass(fieldError?.field === 'confirm')}
                      aria-invalid={fieldError?.field === 'confirm'}
                      aria-describedby={fieldError?.field === 'confirm' ? 'confirm-error' : undefined}
                      disabled={sending}
                    />
                    {fieldMessage('confirm')}
                  </div>
                </>
              )}

              <button
                type="submit"
                disabled={sending}
                className="w-full py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {sending ? 'Wysyłam…' : submitLabel}
              </button>

              <button
                type="button"
                onClick={() => onNavigate('login')}
                className="w-full min-h-[44px] text-sm font-semibold text-neutral-400 hover:text-neutral-200"
              >
                Wróć do logowania
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default PasswordResetPage;
