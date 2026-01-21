/**
 * Profile Page - User settings and preferences
 */

import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { AVAILABLE_LOCATIONS, UserTier } from '../../types';

interface ProfilePageProps {
  onNavigate: (section: 'dashboard' | 'premium') => void;
}

const ProfilePage: React.FC<ProfilePageProps> = ({ onNavigate }) => {
  const { user, updateProfile, changePassword, logout, isLoading, error, clearError, isPremium } = useAuth();

  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'preferences'>('profile');
  const [successMessage, setSuccessMessage] = useState('');

  // Profile form
  const [profileData, setProfileData] = useState({
    full_name: user?.full_name || '',
    location: user?.location || 'Rybno',
  });

  // Password form
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const [localError, setLocalError] = useState('');

  const showSuccess = (message: string) => {
    setSuccessMessage(message);
    setTimeout(() => setSuccessMessage(''), 3000);
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    try {
      await updateProfile({
        full_name: profileData.full_name,
        location: profileData.location,
      });
      showSuccess('Profil zaktualizowany!');
    } catch {
      // Error handled by context
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    if (passwordData.newPassword !== passwordData.confirmPassword) {
      setLocalError('Nowe hasła nie są identyczne');
      return;
    }

    if (passwordData.newPassword.length < 8) {
      setLocalError('Hasło musi mieć minimum 8 znaków');
      return;
    }

    try {
      await changePassword(passwordData.currentPassword, passwordData.newPassword);
      setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
      showSuccess('Hasło zmienione!');
    } catch {
      // Error handled by context
    }
  };

  const handleLogout = async () => {
    await logout();
    onNavigate('dashboard');
  };

  const getTierBadge = (tier: UserTier) => {
    switch (tier) {
      case 'premium':
        return (
          <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-bold">
            Premium
          </span>
        );
      case 'business':
        return (
          <span className="px-3 py-1 bg-slate-800 text-white rounded-full text-sm font-bold">
            Business
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 bg-slate-100 text-slate-600 rounded-full text-sm font-medium">
            Free
          </span>
        );
    }
  };

  if (!user) {
    return (
      <div className="p-8 text-center">
        <p>Musisz być zalogowany</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-black mb-2">Ustawienia konta</h1>
        <p className="text-slate-500">Zarządzaj swoim profilem i preferencjami</p>
      </div>

      {/* Success message */}
      {successMessage && (
        <div className="mb-6 p-4 bg-green-50 border border-green-100 rounded-xl text-green-600 text-sm">
          {successMessage}
        </div>
      )}

      {/* Error message */}
      {(error || localError) && (
        <div className="mb-6 p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm">
          {error || localError}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Sidebar */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-2xl p-6 border border-slate-100 sticky top-24">
            {/* User info */}
            <div className="text-center mb-6">
              <div className="w-20 h-20 rounded-full bg-blue-100 flex items-center justify-center font-bold text-blue-600 text-2xl mx-auto mb-3">
                {user.full_name.split(' ').map(n => n[0]).join('').toUpperCase()}
              </div>
              <h3 className="font-bold text-lg">{user.full_name}</h3>
              <p className="text-slate-400 text-sm">{user.email}</p>
              <div className="mt-2">{getTierBadge(user.tier as UserTier)}</div>
            </div>

            {/* Navigation */}
            <nav className="space-y-1">
              <button
                onClick={() => setActiveTab('profile')}
                className={`w-full text-left px-4 py-3 rounded-xl transition-colors ${
                  activeTab === 'profile'
                    ? 'bg-blue-50 text-blue-600 font-semibold'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                Profil
              </button>
              <button
                onClick={() => setActiveTab('password')}
                className={`w-full text-left px-4 py-3 rounded-xl transition-colors ${
                  activeTab === 'password'
                    ? 'bg-blue-50 text-blue-600 font-semibold'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                Hasło
              </button>
              <button
                onClick={() => setActiveTab('preferences')}
                className={`w-full text-left px-4 py-3 rounded-xl transition-colors ${
                  activeTab === 'preferences'
                    ? 'bg-blue-50 text-blue-600 font-semibold'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                Preferencje
              </button>
            </nav>

            <hr className="my-4 border-slate-100" />

            {/* Logout */}
            <button
              onClick={handleLogout}
              className="w-full text-left px-4 py-3 rounded-xl text-red-600 hover:bg-red-50 transition-colors"
            >
              Wyloguj się
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="lg:col-span-3">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="bg-white rounded-2xl p-8 border border-slate-100">
              <h2 className="text-xl font-bold mb-6">Dane profilu</h2>

              <form onSubmit={handleProfileSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Imię i nazwisko
                  </label>
                  <input
                    type="text"
                    value={profileData.full_name}
                    onChange={(e) =>
                      setProfileData((p) => ({ ...p, full_name: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                    disabled={isLoading}
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Email
                  </label>
                  <input
                    type="email"
                    value={user.email}
                    disabled
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 text-slate-500"
                  />
                  <p className="text-xs text-slate-400 mt-1">
                    Email nie może być zmieniony
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Miejscowość
                  </label>
                  <select
                    value={profileData.location}
                    onChange={(e) =>
                      setProfileData((p) => ({ ...p, location: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all bg-white"
                    disabled={isLoading}
                  >
                    {AVAILABLE_LOCATIONS.map((loc) => (
                      <option key={loc} value={loc}>
                        {loc}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-slate-400 mt-1">
                    Twoja lokalizacja wpływa na spersonalizowane informacje (pogoda,
                    wydarzenia, wywóz śmieci)
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="px-6 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {isLoading ? 'Zapisywanie...' : 'Zapisz zmiany'}
                </button>
              </form>
            </div>
          )}

          {/* Password Tab */}
          {activeTab === 'password' && (
            <div className="bg-white rounded-2xl p-8 border border-slate-100">
              <h2 className="text-xl font-bold mb-6">Zmiana hasła</h2>

              <form onSubmit={handlePasswordSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Aktualne hasło
                  </label>
                  <input
                    type="password"
                    value={passwordData.currentPassword}
                    onChange={(e) =>
                      setPasswordData((p) => ({ ...p, currentPassword: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                    disabled={isLoading}
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Nowe hasło
                  </label>
                  <input
                    type="password"
                    value={passwordData.newPassword}
                    onChange={(e) =>
                      setPasswordData((p) => ({ ...p, newPassword: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                    disabled={isLoading}
                  />
                  <p className="text-xs text-slate-400 mt-1">
                    Min. 8 znaków, wielka litera i cyfra
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Potwierdź nowe hasło
                  </label>
                  <input
                    type="password"
                    value={passwordData.confirmPassword}
                    onChange={(e) =>
                      setPasswordData((p) => ({ ...p, confirmPassword: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                    disabled={isLoading}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="px-6 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {isLoading ? 'Zmieniam...' : 'Zmień hasło'}
                </button>
              </form>
            </div>
          )}

          {/* Preferences Tab */}
          {activeTab === 'preferences' && (
            <div className="space-y-6">
              {/* Subscription */}
              <div className="bg-white rounded-2xl p-8 border border-slate-100">
                <h2 className="text-xl font-bold mb-4">Subskrypcja</h2>

                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
                  <div>
                    <p className="font-semibold">
                      Plan: {getTierBadge(user.tier as UserTier)}
                    </p>
                    <p className="text-sm text-slate-500 mt-1">
                      {isPremium
                        ? 'Masz dostęp do wszystkich funkcji Premium'
                        : 'Uaktualnij do Premium, aby odblokować więcej funkcji'}
                    </p>
                  </div>
                  {!isPremium && (
                    <button
                      onClick={() => onNavigate('premium')}
                      className="px-4 py-2 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-colors"
                    >
                      Ulepsz
                    </button>
                  )}
                </div>
              </div>

              {/* Newsletter */}
              <div className="bg-white rounded-2xl p-8 border border-slate-100">
                <h2 className="text-xl font-bold mb-4">Newsletter</h2>

                <div className="space-y-4">
                  <label className="flex items-center justify-between p-4 bg-slate-50 rounded-xl cursor-pointer">
                    <div>
                      <p className="font-semibold">Newsletter tygodniowy</p>
                      <p className="text-sm text-slate-500">
                        Podsumowanie tygodnia co sobotę
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      defaultChecked
                      className="w-5 h-5 rounded text-blue-600"
                    />
                  </label>

                  <label
                    className={`flex items-center justify-between p-4 rounded-xl ${
                      isPremium
                        ? 'bg-slate-50 cursor-pointer'
                        : 'bg-slate-100/50 cursor-not-allowed'
                    }`}
                  >
                    <div>
                      <p className="font-semibold flex items-center gap-2">
                        Newsletter dzienny
                        {!isPremium && (
                          <span className="text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded">
                            Premium
                          </span>
                        )}
                      </p>
                      <p className="text-sm text-slate-500">
                        Poranny briefing pon-pt o 6:30
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      disabled={!isPremium}
                      className="w-5 h-5 rounded text-blue-600 disabled:opacity-50"
                    />
                  </label>
                </div>
              </div>

              {/* Account info */}
              <div className="bg-white rounded-2xl p-8 border border-slate-100">
                <h2 className="text-xl font-bold mb-4">Informacje o koncie</h2>

                <dl className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Data rejestracji</dt>
                    <dd className="font-medium">
                      {new Date(user.created_at).toLocaleDateString('pl-PL')}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Ostatnie logowanie</dt>
                    <dd className="font-medium">
                      {user.last_login
                        ? new Date(user.last_login).toLocaleString('pl-PL')
                        : '-'}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Email zweryfikowany</dt>
                    <dd className="font-medium">
                      {user.email_verified ? (
                        <span className="text-green-600">Tak</span>
                      ) : (
                        <span className="text-amber-600">Nie</span>
                      )}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
