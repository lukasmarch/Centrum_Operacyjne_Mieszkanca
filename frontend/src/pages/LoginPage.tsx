/**
 * Login Page
 */

import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface LoginPageProps {
  onNavigate: (page: 'register' | 'dashboard') => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onNavigate }) => {
  const { login, isLoading, error, clearError } = useAuth();

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

    try {
      await login({ email, password });
      onNavigate('dashboard');
    } catch {
      // Error is handled by AuthContext
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center font-bold text-3xl text-white mx-auto mb-4 shadow-lg shadow-blue-500/30">
            D
          </div>
          <h1 className="text-3xl font-black mb-2 text-neutral-100">Witaj ponownie!</h1>
          <p className="text-neutral-400">Zaloguj się do Centrum Operacyjnego</p>
        </div>

        {/* Form */}
        <div className="bg-gray-950/50 backdrop-blur-xl rounded-3xl p-8 shadow-xl border border-gray-800/50">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Error message */}
            {(error || localError) && (
              <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                {error || localError}
              </div>
            )}

            {/* Email */}
            <div>
              <label className="block text-sm font-semibold text-neutral-300 mb-2">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="twoj@email.pl"
                className="w-full px-4 py-3 rounded-xl bg-gray-900 border border-gray-700/50 text-neutral-100 placeholder-neutral-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                disabled={isLoading}
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-semibold text-neutral-300 mb-2">
                Hasło
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-4 py-3 rounded-xl bg-gray-900 border border-gray-700/50 text-neutral-100 placeholder-neutral-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                disabled={isLoading}
              />
            </div>

            {/* Forgot password */}
            <div className="flex justify-end">
              <button
                type="button"
                className="text-sm text-blue-400 hover:text-blue-300 font-medium"
              >
                Zapomniałeś hasła?
              </button>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                  Logowanie...
                </span>
              ) : (
                'Zaloguj się'
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-8">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-800/50"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-gray-950 text-neutral-500 rounded-full">lub</span>
            </div>
          </div>

          {/* Register link */}
          <p className="text-center text-neutral-400">
            Nie masz jeszcze konta?{' '}
            <button
              onClick={() => onNavigate('register')}
              className="text-blue-400 font-bold hover:text-blue-300"
            >
              Zarejestruj się
            </button>
          </p>
        </div>

        {/* Footer */}
        <p className="text-center text-neutral-500 text-sm mt-6">
          Logując się, akceptujesz{' '}
          <a href="#" className="text-blue-400 hover:underline">
            Regulamin
          </a>{' '}
          i{' '}
          <a href="#" className="text-blue-400 hover:underline">
            Politykę prywatności
          </a>
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
