/**
 * Profile Page - User settings and preferences
 */

import React, { useState } from 'react';
import { Camera } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { AVAILABLE_LOCATIONS, UserTier } from '../../types';
import { usePushNotifications } from '../hooks/usePushNotifications';
import { DASHBOARD_LAYOUTS, DashboardLayoutId, TileId, getUserDashboardLayout } from '../config/dashboardLayouts';

interface ProfilePageProps {
  onNavigate: (section: 'dashboard' | 'premium') => void;
}

const ProfilePage: React.FC<ProfilePageProps> = ({ onNavigate }) => {
  const { user, updateProfile, changePassword, logout, isLoading, error, clearError, isPremium } = useAuth();
  const { status: pushStatus, isSubscribed: pushSubscribed, isSupported: pushSupported, subscribe: pushSubscribe, unsubscribe: pushUnsubscribe } = usePushNotifications();
  const [pushLoading, setPushLoading] = useState(false);

  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'preferences'>('profile');
  const [successMessage, setSuccessMessage] = useState('');

  // Profile form
  const [profileData, setProfileData] = useState({
    full_name: user?.full_name || '',
    location: user?.location || 'Rybno',
    avatarUrl: user?.avatarUrl || '',
  });

  // Password form
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const [localError, setLocalError] = useState('');

  // Dashboard layout state
  const [selectedLayout, setSelectedLayout] = useState<DashboardLayoutId>(
    getUserDashboardLayout(user?.preferences ?? null)
  );
  const [layoutSaving, setLayoutSaving] = useState(false);

  const showSuccess = (message: string) => {
    setSuccessMessage(message);
    setTimeout(() => setSuccessMessage(''), 3000);
  };

  const handleLayoutSelect = async (layoutId: DashboardLayoutId) => {
    const previousLayout = selectedLayout;
    setSelectedLayout(layoutId);
    setLayoutSaving(true);
    clearError();
    try {
      await updateProfile({ preferences: { dashboard_layout: layoutId } });
      showSuccess('Układ dashboardu zapisany');
    } catch {
      setSelectedLayout(previousLayout); // revert on error
    } finally {
      setLayoutSaving(false);
    }
  };

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 2 * 1024 * 1024) {
        setLocalError('Plik jest za duży. Maksymalny rozmiar to 2MB.');
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        setProfileData(p => ({ ...p, avatarUrl: reader.result as string }));
      };
      reader.readAsDataURL(file);
    }
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    try {
      await updateProfile({
        full_name: profileData.full_name,
        location: profileData.location,
        avatarUrl: profileData.avatarUrl,
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
          <span className="px-3 py-1 bg-gray-900 text-white rounded-full text-sm font-bold">
            Business
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 bg-gray-950 text-neutral-600 rounded-full text-sm font-medium">
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
        <p className="text-neutral-500">Zarządzaj swoim profilem i preferencjami</p>
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
          <div className="bg-gray-950 rounded-2xl p-6 border border-gray-800/50 sticky top-24">
            {/* User info */}
            <div className="text-center mb-6">
              {user.avatarUrl ? (
                <img src={user.avatarUrl} alt="Avatar" className="w-20 h-20 rounded-full object-cover mx-auto mb-3 border border-gray-800/50" />
              ) : (
                <div className="w-20 h-20 rounded-full bg-blue-100 flex items-center justify-center font-bold text-blue-600 text-2xl mx-auto mb-3">
                  {user.full_name.split(' ').map(n => n[0]).join('').toUpperCase()}
                </div>
              )}
              <h3 className="font-bold text-lg">{user.full_name}</h3>
              <p className="text-neutral-400 text-sm">{user.email}</p>
              <div className="mt-2">{getTierBadge(user.tier as UserTier)}</div>
            </div>

            {/* Navigation */}
            <nav className="space-y-1">
              <button
                onClick={() => setActiveTab('profile')}
                className={`w-full text-left px-4 py-3 rounded-xl transition-colors ${
                  activeTab === 'profile'
                    ? 'bg-blue-50 text-blue-600 font-semibold'
                    : 'text-neutral-600 hover:bg-gray-950'
                }`}
              >
                Profil
              </button>
              <button
                onClick={() => setActiveTab('password')}
                className={`w-full text-left px-4 py-3 rounded-xl transition-colors ${
                  activeTab === 'password'
                    ? 'bg-blue-50 text-blue-600 font-semibold'
                    : 'text-neutral-600 hover:bg-gray-950'
                }`}
              >
                Hasło
              </button>
              <button
                onClick={() => setActiveTab('preferences')}
                className={`w-full text-left px-4 py-3 rounded-xl transition-colors ${
                  activeTab === 'preferences'
                    ? 'bg-blue-50 text-blue-600 font-semibold'
                    : 'text-neutral-600 hover:bg-gray-950'
                }`}
              >
                Preferencje
              </button>
            </nav>

            <hr className="my-4 border-gray-800/50" />

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
            <div className="bg-gray-950 rounded-2xl p-8 border border-gray-800/50">
              <h2 className="text-xl font-bold mb-6">Dane profilu</h2>

              <form onSubmit={handleProfileSubmit} className="space-y-6">
                
                {/* Avatar Upload */}
                <div className="flex items-center gap-6 mb-8">
                  <div className="relative">
                    {profileData.avatarUrl ? (
                      <img 
                        src={profileData.avatarUrl} 
                        alt="Avatar preview" 
                        className="w-24 h-24 rounded-full object-cover border-4 border-gray-800/50"
                      />
                    ) : (
                      <div className="w-24 h-24 rounded-full bg-blue-100 flex items-center justify-center font-bold text-blue-600 text-3xl border-4 border-gray-800/50">
                        {user.full_name.split(' ').map(n => n[0]).join('').toUpperCase()}
                      </div>
                    )}
                    <label className="absolute bottom-0 right-0 bg-blue-600 p-2 rounded-full cursor-pointer hover:bg-blue-700 transition-colors shadow-lg">
                      <Camera size={16} className="text-white" />
                      <input type="file" className="hidden" accept="image/*" onChange={handleAvatarChange} />
                    </label>
                  </div>
                  <div>
                    <h3 className="font-bold text-lg">Zmień zdjęcie profilowe</h3>
                    <p className="text-sm text-neutral-500">JPG, PNG lub GIF. Max 2MB.</p>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-neutral-300 mb-2">
                    Imię i nazwisko
                  </label>
                  <input
                    type="text"
                    value={profileData.full_name}
                    onChange={(e) =>
                      setProfileData((p) => ({ ...p, full_name: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-gray-800/50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                    disabled={isLoading}
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-neutral-300 mb-2">
                    Email
                  </label>
                  <input
                    type="email"
                    value={user.email}
                    disabled
                    className="w-full px-4 py-3 rounded-xl border border-gray-800/50 bg-gray-950 text-neutral-500"
                  />
                  <p className="text-xs text-neutral-400 mt-1">
                    Email nie może być zmieniony
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-neutral-300 mb-2">
                    Miejscowość
                  </label>
                  <select
                    value={profileData.location}
                    onChange={(e) =>
                      setProfileData((p) => ({ ...p, location: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-gray-800/50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all bg-gray-950"
                    disabled={isLoading}
                  >
                    {AVAILABLE_LOCATIONS.map((loc) => (
                      <option key={loc} value={loc}>
                        {loc}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-neutral-400 mt-1">
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
            <div className="bg-gray-950 rounded-2xl p-8 border border-gray-800/50">
              <h2 className="text-xl font-bold mb-6">Zmiana hasła</h2>

              <form onSubmit={handlePasswordSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-semibold text-neutral-300 mb-2">
                    Aktualne hasło
                  </label>
                  <input
                    type="password"
                    value={passwordData.currentPassword}
                    onChange={(e) =>
                      setPasswordData((p) => ({ ...p, currentPassword: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-gray-800/50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                    disabled={isLoading}
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-neutral-300 mb-2">
                    Nowe hasło
                  </label>
                  <input
                    type="password"
                    value={passwordData.newPassword}
                    onChange={(e) =>
                      setPasswordData((p) => ({ ...p, newPassword: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-gray-800/50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                    disabled={isLoading}
                  />
                  <p className="text-xs text-neutral-400 mt-1">
                    Min. 8 znaków, wielka litera i cyfra
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-neutral-300 mb-2">
                    Potwierdź nowe hasło
                  </label>
                  <input
                    type="password"
                    value={passwordData.confirmPassword}
                    onChange={(e) =>
                      setPasswordData((p) => ({ ...p, confirmPassword: e.target.value }))
                    }
                    className="w-full px-4 py-3 rounded-xl border border-gray-800/50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
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
              <div className="bg-gray-950 rounded-2xl p-8 border border-gray-800/50">
                <h2 className="text-xl font-bold mb-4">Subskrypcja</h2>

                <div className="flex items-center justify-between p-4 bg-gray-950 rounded-xl">
                  <div>
                    <p className="font-semibold">
                      Plan: {getTierBadge(user.tier as UserTier)}
                    </p>
                    <p className="text-sm text-neutral-500 mt-1">
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

              {/* Dashboard Layout Presets */}
              <div className="bg-gray-950 rounded-2xl p-8 border border-gray-800/50">
                <h2 className="text-xl font-bold mb-2">Układ dashboardu</h2>
                <p className="text-sm text-neutral-500 mb-6">
                  Wybierz układ kafelków na stronie głównej
                </p>

                {isPremium ? (
                  <div className="grid grid-cols-2 gap-4">
                    {(Object.values(DASHBOARD_LAYOUTS) as typeof DASHBOARD_LAYOUTS[DashboardLayoutId][]).map((layout) => {
                      const TILE_COLORS: Record<TileId, string> = {
                        ai_briefing: 'bg-blue-400',
                        weather:     'bg-sky-400',
                        traffic:     'bg-orange-400',
                        events:      'bg-violet-400',
                        airly:       'bg-emerald-400',
                        gmina:       'bg-rose-400',
                        news:        'bg-gray-400',
                      };

                      const MiniGridPreview = () => (
                        <div className="grid grid-cols-4 gap-0.5 h-12 mb-3">
                          {layout.tiles.map((tile) => (
                            <div
                              key={tile.id}
                              title={tile.id}
                              style={{
                                gridColumn: `span ${Math.min(tile.colSpan, 4)}`,
                                gridRow: tile.rowSpan ? `span ${tile.rowSpan}` : undefined,
                              }}
                              className={`rounded-sm ${TILE_COLORS[tile.id]} opacity-80`}
                            />
                          ))}
                        </div>
                      );

                      const isActive = selectedLayout === layout.id;

                      return (
                        <button
                          key={layout.id}
                          onClick={() => handleLayoutSelect(layout.id)}
                          disabled={layoutSaving}
                          className={`text-left p-4 rounded-xl border-2 transition-all disabled:opacity-60 ${
                            isActive
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-gray-800/50 hover:border-gray-700 bg-gray-950'
                          }`}
                        >
                          <MiniGridPreview />
                          <p className="font-semibold text-sm text-neutral-200">{layout.name}</p>
                          <p className="text-xs text-neutral-500 mt-0.5">{layout.description}</p>
                          {isActive && (
                            <p className="text-xs text-blue-600 font-semibold mt-1">
                              {layoutSaving ? 'Zapisywanie...' : 'Aktywny'}
                            </p>
                          )}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="relative">
                    <div className="grid grid-cols-2 gap-4 opacity-40 pointer-events-none select-none">
                      {(Object.values(DASHBOARD_LAYOUTS) as typeof DASHBOARD_LAYOUTS[DashboardLayoutId][]).map((layout) => (
                        <div
                          key={layout.id}
                          className="p-4 rounded-xl border-2 border-gray-800/50 bg-gray-950"
                        >
                          <div className="grid grid-cols-4 gap-0.5 h-12 mb-3">
                            {layout.tiles.map((tile) => (
                              <div
                                key={tile.id}
                                style={{ gridColumn: `span ${Math.min(tile.colSpan, 4)}` }}
                                className="rounded-sm bg-gray-300"
                              />
                            ))}
                          </div>
                          <p className="font-semibold text-sm text-neutral-200">{layout.name}</p>
                        </div>
                      ))}
                    </div>
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                      <div className="text-center bg-gray-950/90 px-6 py-4 rounded-2xl shadow-sm border border-gray-800/50">
                        <p className="text-neutral-300 font-semibold mb-1">Funkcja Premium</p>
                        <p className="text-neutral-500 text-sm mb-3">
                          Wybierz układ dashboardu z planem Premium
                        </p>
                        <button
                          onClick={() => onNavigate('premium')}
                          className="px-5 py-2 bg-blue-600 text-white text-sm font-bold rounded-xl hover:bg-blue-700 transition-colors"
                        >
                          Ulepsz do Premium
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Newsletter */}
              <div className="bg-gray-950 rounded-2xl p-8 border border-gray-800/50">
                <h2 className="text-xl font-bold mb-4">Newsletter</h2>

                <div className="space-y-4">
                  <label className="flex items-center justify-between p-4 bg-gray-950 rounded-xl cursor-pointer">
                    <div>
                      <p className="font-semibold">Newsletter tygodniowy</p>
                      <p className="text-sm text-neutral-500">
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
                        ? 'bg-gray-950 cursor-pointer'
                        : 'bg-gray-950/50 cursor-not-allowed'
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
                      <p className="text-sm text-neutral-500">
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

              {/* Push Notifications */}
              <div className="bg-gray-950 rounded-2xl p-8 border border-gray-800/50">
                <h2 className="text-xl font-bold mb-4">Powiadomienia push</h2>

                {!pushSupported ? (
                  <div className="p-4 bg-gray-950 rounded-xl text-neutral-500 text-sm">
                    Twoja przeglądarka nie obsługuje powiadomień push.
                  </div>
                ) : pushStatus === 'denied' ? (
                  <div className="p-4 bg-amber-50 border border-amber-100 rounded-xl text-amber-700 text-sm">
                    Powiadomienia zostały zablokowane w ustawieniach przeglądarki.
                    Zmień pozwolenia ręcznie aby je włączyć.
                  </div>
                ) : (
                  <div className="space-y-4">
                    <label className="flex items-center justify-between p-4 bg-gray-950 rounded-xl cursor-pointer">
                      <div>
                        <p className="font-semibold">Alerty bezpieczeństwa</p>
                        <p className="text-sm text-neutral-500">
                          Pożary, wypadki – natychmiastowe powiadomienia
                        </p>
                        <p className="text-xs text-green-600 mt-0.5">Dostępne bezpłatnie</p>
                      </div>
                      <button
                        onClick={async () => {
                          setPushLoading(true);
                          if (pushSubscribed) {
                            await pushUnsubscribe();
                          } else {
                            await pushSubscribe(['alerty', 'powietrze', 'artykuly']);
                          }
                          setPushLoading(false);
                        }}
                        disabled={pushLoading || pushStatus === 'loading'}
                        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                          pushSubscribed ? 'bg-blue-600' : 'bg-gray-200'
                        } disabled:opacity-50`}
                        role="switch"
                        aria-checked={pushSubscribed}
                      >
                        <span
                          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                            pushSubscribed ? 'translate-x-5' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </label>

                    {pushSubscribed && (
                      <p className="text-xs text-neutral-500 px-1">
                        Powiadomienia włączone. Otrzymasz alerty o pożarach, wypadkach, smogu i dziennym podsumowaniu.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Account info */}
              <div className="bg-gray-950 rounded-2xl p-8 border border-gray-800/50">
                <h2 className="text-xl font-bold mb-4">Informacje o koncie</h2>

                <dl className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-neutral-500">Data rejestracji</dt>
                    <dd className="font-medium">
                      {new Date(user.created_at).toLocaleDateString('pl-PL')}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-neutral-500">Ostatnie logowanie</dt>
                    <dd className="font-medium">
                      {user.last_login
                        ? new Date(user.last_login).toLocaleString('pl-PL')
                        : '-'}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-neutral-500">Email zweryfikowany</dt>
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
