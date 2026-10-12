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
import { Notice, PageHead } from '../../components/simple/tv';

interface PasswordResetPageProps {
  onNavigate: (page: 'login' | 'dashboard') => void;
}

const tokenFromUrl = () => new URLSearchParams(window.location.search).get('token') ?? '';

// Te same miary co logowanie: pole 52 px, tekst 16 px, błąd = obrys żółty (kolor = stan)
const inputClass = (invalid: boolean) =>
  `min-h-[52px] w-full border-2 ${invalid ? 'border-tv-yellow' : 'border-tv-seam'} bg-tv-ink px-4 text-[16px] text-white outline-none transition-colors placeholder:text-tv-muted focus:border-tv-paper disabled:opacity-60`;
const LABEL = 'mb-1.5 block text-[15px] font-semibold text-tv-paper';
const PRIMARY =
  'font-cond min-h-[52px] w-full bg-tv-blue px-4 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-not-allowed disabled:opacity-50';
const LINK = 'min-h-[44px] text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline';

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
      <p id={`${field}-error`} role="alert" className="mt-1.5 text-[14px] font-semibold text-tv-yellow">{fieldError.message}</p>
    ) : null;

  const submitLabel = token ? 'Ustaw nowe hasło' : 'Wyślij link';

  return (
    <div className="flex min-h-[70vh] items-center justify-center py-8">
      <div className="w-full max-w-md space-y-5">
        <PageHead
          title={token ? 'Ustaw nowe hasło' : 'Nie pamiętasz hasła?'}
          sub={token
            ? 'Po zapisaniu wylogujemy wszystkie inne urządzenia.'
            : 'Podaj adres konta — wyślemy link do ustawienia nowego hasła.'}
        />

        <div className="border-t-2 border-tv-blue bg-tv-panel p-5 sm:p-6">
          {sentMessage ? (
            <div role="status" className="space-y-4">
              <p className="text-[16px] leading-relaxed text-[#d7dbe8]">{sentMessage}</p>
              <p className="text-[15px] text-tv-muted">
                Nie widzisz maila? Sprawdź folder „Oferty” lub „Spam”.
              </p>
              <button
                type="button"
                onClick={() => onNavigate('login')}
                className={LINK}
              >
                Wróć do logowania
              </button>
            </div>
          ) : linkDead ? (
            <div role="alert" className="space-y-4">
              <p className="text-[16px] leading-relaxed text-[#d7dbe8]">
                Ten link wygasł albo został już użyty. Link działa przez godzinę i tylko raz.
              </p>
              <button
                type="button"
                onClick={() => { setLinkDead(false); window.location.assign('/nowe-haslo'); }}
                className={PRIMARY}
              >
                Poproś o nowy link
              </button>
            </div>
          ) : (
            <form onSubmit={token ? setNewPassword : requestLink} className="space-y-5" noValidate>
              {error && (
                <Notice tone="warn" role="alert">{error}</Notice>
              )}

              {!token ? (
                <div>
                  <label htmlFor="reset-email" className={LABEL}>
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
                    <label htmlFor="reset-password" className={LABEL}>
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
                    <p className="mt-1.5 text-[13px] leading-snug text-tv-muted">Min. 8 znaków, wielka litera i cyfra</p>
                  </div>
                  <div>
                    <label htmlFor="reset-confirm" className={LABEL}>
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
                className={PRIMARY}
              >
                {sending ? 'Wysyłam…' : submitLabel}
              </button>

              <button
                type="button"
                onClick={() => onNavigate('login')}
                className={`${LINK} w-full`}
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
