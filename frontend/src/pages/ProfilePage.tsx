/**
 * Profile Page - User settings and preferences
 */

import React, { useState, useEffect } from 'react';
import { Camera, Check, LogOut } from 'lucide-react';
import { Notice, PageHead, Select, Skeleton, Tag, TagTone } from '../../components/simple/tv';
import { useAuth } from '../context/AuthContext';
import { AVAILABLE_LOCATIONS, UserTier } from '../../types';
import { usePushNotifications } from '../hooks/usePushNotifications';
import PricingCards from '../../components/PricingCards';
import MyBusinessPanel from '../../components/MyBusinessPanel';
import SolectwoPanel from '../../components/SolectwoPanel';
import SolectwaAdminPanel from '../../components/SolectwaAdminPanel';
import { MyRole, PERM_SOLECTWO_POST, fetchMyRoles } from '../services/solectwaApi';
import { getAccessToken } from '../services/authApi';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Język „Paska informacyjnego”: pole 52 px z tekstem 16 px (iOS nie powiększa),
// kąty proste, fokus = obrys papieru. Przycisk główny chabrowy, drugorzędny papierowy
const LABEL = 'mb-1.5 block text-[15px] font-semibold text-tv-paper';
const INPUT =
  'min-h-[52px] w-full border-2 border-tv-seam bg-tv-ink px-4 text-[16px] text-white outline-none transition-colors placeholder:text-tv-muted focus:border-tv-paper disabled:opacity-60';
const HINT = 'mt-1.5 text-[13px] leading-snug text-tv-muted';
const PRIMARY =
  'font-cond min-h-[52px] bg-tv-blue px-6 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-not-allowed disabled:opacity-50';
const SECONDARY =
  'min-h-[44px] whitespace-nowrap bg-tv-paper px-4 text-[15px] font-bold text-tv-ink transition-colors hover:bg-white disabled:opacity-50';
const LINK = 'font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline';

/** Sekcja ustawień: plakietka JEST nagłówkiem, pod nią panel z chabrową krawędzią */
const Section: React.FC<{ title: string; tone?: TagTone; aside?: React.ReactNode; children: React.ReactNode }> = ({
  title, tone = 'blue', aside, children,
}) => (
  <section aria-label={title}>
    <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-1">
      <Tag as="h2" tone={tone}>{title}</Tag>
      {aside && <div className="pb-1">{aside}</div>}
    </div>
    <div className={`border-t-2 bg-tv-panel p-5 sm:p-6 ${tone === 'blue' ? 'border-tv-blue' : 'border-tv-seam'}`}>
      {children}
    </div>
  </section>
);

/** Kwadratowe pole wyboru 24 px — natywny checkbox bez wyglądu, znaczek z lucide */
const SquareCheck: React.FC<{ checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }> = ({
  checked, onChange, disabled,
}) => (
  <span className="relative inline-flex h-6 w-6 shrink-0">
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

interface ProfilePageProps {
  onNavigate: (section: 'dashboard' | 'premium' | 'terms' | 'privacy' | 'business') => void;
  initialTab?: 'profile' | 'password' | 'preferences' | 'subscription' | 'polecaj' | 'firma' | 'solectwo' | 'solectwa-admin';
}

/** Ile pełnych dni okresu próbnego zostało; null, gdy trial nie działa.
 *
 *  Do 20.08.2026 front nie znał słowa „trial": pokazywał sam plan Premium, więc
 *  użytkownik nie wiedział, że ma go na 30 dni, i nie miał powodu niczego kupić —
 *  cennik oferował mu to, co już miał. */
const trialDaysLeft = (trialEndsAt?: string | null): number | null => {
  if (!trialEndsAt) return null;
  // Backend zapisuje czas w UTC bez sufiksu strefy — bez „Z" przeglądarka
  // potraktowałaby go jako lokalny i doba potrafiłaby zniknąć.
  const iso = /[Zz]|[+-]\d{2}:\d{2}$/.test(trialEndsAt) ? trialEndsAt : `${trialEndsAt}Z`;
  const end = new Date(iso).getTime();
  if (Number.isNaN(end)) return null;
  const days = Math.ceil((end - Date.now()) / 86_400_000);
  return days > 0 ? days : null;
};

const formatTrialEnd = (trialEndsAt: string): string => {
  const iso = /[Zz]|[+-]\d{2}:\d{2}$/.test(trialEndsAt) ? trialEndsAt : `${trialEndsAt}Z`;
  return new Date(iso).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long' });
};

const NewsletterPrefs: React.FC<{ isPremium: boolean; apiBase: string }> = ({ isPremium, apiBase }) => {
  // `subscribed === null` = jeszcze nie wiemy. Wcześniej brak subskrypcji (404) był
  // pokazywany jako włączony tygodnik — użytkownik widział zaznaczony checkbox
  // i nie dostawał żadnego maila.
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [daily, setDaily] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { setSubscribed(false); return; }
    fetch(`${apiBase}/newsletter/my-subscription`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        setSubscribed(Boolean(data));
        setDaily(data?.frequency === 'daily');
      })
      .catch(() => { setSubscribed(false); });
  }, [apiBase]);

  const save = async (frequency: 'daily' | 'weekly') => {
    const token = getAccessToken();
    if (!token) return;
    setSaving(true);
    const res = await fetch(`${apiBase}/newsletter/my-subscription`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ frequency }),
    }).catch(() => null);
    setSaving(false);
    if (res?.ok) {
      setSubscribed(true);
      setDaily(frequency === 'daily');
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  };

  if (subscribed === null) return (
    <Section title="Newsletter">
      <Skeleton className="h-20" />
    </Section>
  );

  return (
    <Section
      title="Newsletter"
      aside={<>
        {saving && <span className="text-[13px] text-tv-muted">Zapisywanie...</span>}
        {saved && !saving && (
          <span className="inline-flex items-center gap-1 text-[13px] text-tv-paper">
            <Check size={15} className="text-tv-green" aria-hidden /> Zapisano
          </span>
        )}
      </>}
    >
      {!subscribed ? (
        <div>
          <p className="text-[16px] font-semibold text-white">Newsletter jest wyłączony</p>
          <p className="mt-1 text-[15px] leading-snug text-[#d7dbe8]">
            Nie wysyłamy Ci żadnych podsumowań. Możesz to zmienić jednym kliknięciem.
          </p>
          <button
            onClick={() => save(isPremium ? 'daily' : 'weekly')}
            disabled={saving}
            className={`${PRIMARY} mt-4`}
          >
            Włącz {isPremium ? 'poranny briefing' : 'newsletter tygodniowy'}
          </button>
        </div>
      ) : (
        <div className="-mx-5 -mb-5 grid gap-px border-t border-tv-seam bg-tv-seam sm:-mx-6 sm:-mb-6">
          {/* Częstotliwość to jedna wartość w bazie, nie dwie niezależne flagi —
              tygodnik jest podstawą subskrypcji, dzienny go zastępuje. */}
          <div className="flex items-center justify-between gap-4 bg-tv-panel px-5 py-4 sm:px-6">
            <div>
              <p className="text-[16px] font-semibold text-white">Newsletter tygodniowy</p>
              <p className="text-[14px] text-tv-muted">Podsumowanie tygodnia co sobotę</p>
            </div>
            <span className="shrink-0 text-[14px] font-semibold text-tv-paper">
              {daily ? 'zastąpiony dziennym' : 'włączony'}
            </span>
          </div>

          {isPremium ? (
            <label className="flex cursor-pointer items-center justify-between gap-4 bg-tv-panel px-5 py-4 transition-colors hover:bg-tv-panel2 sm:px-6">
              <div>
                <p className="text-[16px] font-semibold text-white">Newsletter dzienny</p>
                <p className="text-[14px] text-tv-muted">Poranny briefing pon–pt o 7:15 — newsy, śmietnik, BIP, pogoda</p>
              </div>
              <SquareCheck
                checked={daily}
                onChange={v => save(v ? 'daily' : 'weekly')}
              />
            </label>
          ) : (
            <div className="flex items-center justify-between gap-4 bg-tv-panel px-5 py-4 sm:px-6">
              <div>
                <p className="text-[16px] font-semibold text-tv-muted">Newsletter dzienny</p>
                <p className="text-[14px] text-tv-muted">Dostępny w planie Premium</p>
              </div>
              <Tag tone="seam">Premium</Tag>
            </div>
          )}
        </div>
      )}
    </Section>
  );
};

const ProfilePage: React.FC<ProfilePageProps> = ({ onNavigate, initialTab }) => {
  const { user, updateProfile, changePassword, logout, isLoading, error, clearError, isPremium } = useAuth();
  const { status: pushStatus, isSubscribed: pushSubscribed, isSupported: pushSupported, subscribe: pushSubscribe, unsubscribe: pushUnsubscribe } = usePushNotifications();
  const [pushLoading, setPushLoading] = useState(false);

  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'preferences' | 'subscription' | 'polecaj' | 'firma' | 'solectwo' | 'solectwa-admin'>(initialTab ?? 'profile');
  const [referralData, setReferralData] = useState<{referral_code: string; referral_link: string; referrals_count: number; reward_per_referral: string} | null>(null);
  const [referralCopied, setReferralCopied] = useState(false);
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

  // Role z zakresem (sołtys). Zakładka „Sołectwo" istnieje tylko dla konta
  // z uprawnieniem do ogłoszeń — reszta mieszkańców jej nie widzi.
  const [roles, setRoles] = useState<MyRole[]>([]);
  useEffect(() => {
    fetchMyRoles().then(setRoles).catch(() => {});
  }, [user?.id]);
  const postingRole = roles.find((r) => r.permissions.includes(PERM_SOLECTWO_POST));


  // Fetch referral data when tab is active
  useEffect(() => {
    if (activeTab !== 'polecaj') return;
    const token = getAccessToken();
    if (!token) return;
    fetch(`${API_BASE_URL}/auth/referral`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(setReferralData)
      .catch(() => {});
  }, [activeTab]);

  const copyReferralLink = () => {
    if (!referralData) return;
    navigator.clipboard.writeText(referralData.referral_link).then(() => {
      setReferralCopied(true);
      setTimeout(() => setReferralCopied(false), 2000);
    });
  };

  const shareReferralLink = () => {
    if (!referralData) return;
    if (navigator.share) {
      navigator.share({
        title: 'Centrum Operacyjne Rybna',
        text: 'Dołącz do Centrum Operacyjnego Rybna i dostań 30 dni Premium za darmo!',
        url: referralData.referral_link,
      });
    } else {
      copyReferralLink();
    }
  };

  const showSuccess = (message: string) => {
    setSuccessMessage(message);
    setTimeout(() => setSuccessMessage(''), 3000);
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

  // ==== RODO / DSAR (art. 15/17/20) ====
  const [exporting, setExporting] = useState(false);
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);

  const handleExportData = async () => {
    const token = getAccessToken();
    if (!token) return;
    setExporting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/users/me/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Eksport nie powiódł się');
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `rybnolive-moje-dane-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showSuccess('Dane wyeksportowane — plik JSON został pobrany.');
    } catch {
      setLocalError('Nie udało się pobrać danych. Spróbuj ponownie.');
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== 'USUŃ') return;
    const token = getAccessToken();
    if (!token) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/users/me`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Usunięcie nie powiodło się');
      await logout();
      onNavigate('dashboard');
    } catch {
      setLocalError('Nie udało się usunąć konta. Skontaktuj się: biuro@lumargo.pl');
      setDeleting(false);
      setDeleteModalOpen(false);
    }
  };

  const daysLeft = trialDaysLeft(user?.trial_ends_at);

  // Plan jako plakietka: okres próbny = żółć (ma termin), Premium = chaber,
  // Firma = papier, darmowy = szew
  const getTierBadge = (tier: UserTier) => {
    switch (tier) {
      case 'premium':
        return daysLeft !== null ? (
          <Tag tone="yellow">Premium &middot; okres próbny</Tag>
        ) : (
          <Tag tone="blue">Premium</Tag>
        );
      case 'business':
        return <Tag tone="paper">Firma lokalna</Tag>;
      default:
        return <Tag tone="seam">Free</Tag>;
    }
  };

  if (!user) {
    return (
      <div className="mx-auto max-w-md py-8">
        <Notice>Musisz być zalogowany</Notice>
      </div>
    );
  }

  const initials = user.full_name.split(' ').map(n => n[0]).join('').toUpperCase();

  // Pozycja menu ustawień: wąski krój jak nawigacja sekcji, aktywna = papier
  const tabClass = (tab: typeof activeTab) =>
    `font-cond flex min-h-[44px] w-full items-center gap-2 px-3 text-left text-[16px] font-bold uppercase tracking-wide transition-colors ${
      activeTab === tab
        ? 'bg-tv-paper text-tv-ink'
        : 'bg-tv-panel text-tv-paper hover:bg-tv-panel2 hover:text-white'
    }`;

  return (
    <div className={`space-y-6 ${activeTab === 'subscription' ? 'max-w-6xl' : 'max-w-4xl'}`}>
      <PageHead title="Ustawienia konta" sub="Zarządzaj swoim profilem i preferencjami" />

      {/* Success message */}
      {successMessage && (
        <p role="status" className="flex items-center gap-2 bg-tv-panel px-4 py-3 text-[15px] text-tv-paper">
          <Check size={17} className="shrink-0 text-tv-green" aria-hidden />
          {successMessage}
        </p>
      )}

      {/* Error message */}
      {(error || localError) && (
        <Notice tone="warn" role="alert">{error || localError}</Notice>
      )}

      <div className={`grid grid-cols-1 gap-6 lg:gap-8 ${activeTab === 'subscription' ? 'lg:grid-cols-5' : 'lg:grid-cols-4'}`}>
        {/* Sidebar */}
        <div className="lg:col-span-1">
          <div className="border-t-2 border-tv-blue bg-tv-panel lg:sticky lg:top-32">
            {/* User info */}
            <div className="flex items-center gap-4 p-4 lg:flex-col lg:items-start">
              {user.avatarUrl ? (
                <img src={user.avatarUrl} alt="Avatar" className="h-16 w-16 shrink-0 object-cover lg:h-20 lg:w-20" />
              ) : (
                <div className="font-cond flex h-16 w-16 shrink-0 items-center justify-center bg-tv-panel2 text-[24px] font-extrabold text-white lg:h-20 lg:w-20">
                  {initials}
                </div>
              )}
              <div className="min-w-0">
                <h2 className="text-[17px] font-bold leading-snug text-white">{user.full_name}</h2>
                <p className="break-all text-[14px] text-tv-muted">{user.email}</p>
                <div className="mt-2">{getTierBadge(user.tier as UserTier)}</div>
                {roles.map((r) => (
                  <p key={r.id} className="mt-2 text-[14px] font-semibold text-tv-paper">{r.signed_as}</p>
                ))}
                {daysLeft !== null && user.trial_ends_at && (
                  <p className="mt-2 text-[13px] leading-relaxed text-tv-muted">
                    do <span className="tabular font-semibold text-tv-paper">{formatTrialEnd(user.trial_ends_at)}</span>
                    {' '}(<span className="tabular">{daysLeft}</span> {daysLeft === 1 ? 'dzień' : 'dni'})
                    <br />
                    potem plan Dla Każdego — nic nie pobieramy
                  </p>
                )}
              </div>
            </div>

            {/* Navigation — na telefonie dwie kolumny, żeby menu nie zjadało ekranu */}
            <nav aria-label="Ustawienia konta" className="grid grid-cols-2 gap-px border-t border-tv-seam bg-tv-seam lg:grid-cols-1">
              <button onClick={() => setActiveTab('profile')} aria-current={activeTab === 'profile' ? 'page' : undefined} className={tabClass('profile')}>
                Profil
              </button>
              <button onClick={() => setActiveTab('password')} aria-current={activeTab === 'password' ? 'page' : undefined} className={tabClass('password')}>
                Hasło
              </button>
              <button onClick={() => setActiveTab('preferences')} aria-current={activeTab === 'preferences' ? 'page' : undefined} className={tabClass('preferences')}>
                Preferencje
              </button>
              <button onClick={() => setActiveTab('subscription')} aria-current={activeTab === 'subscription' ? 'page' : undefined} className={tabClass('subscription')}>
                Subskrypcja
              </button>
              {postingRole && (
                <button onClick={() => setActiveTab('solectwo')} aria-current={activeTab === 'solectwo' ? 'page' : undefined} className={tabClass('solectwo')}>
                  Sołectwo
                </button>
              )}
              {user.is_admin && (
                <button onClick={() => setActiveTab('solectwa-admin')} aria-current={activeTab === 'solectwa-admin' ? 'page' : undefined} className={tabClass('solectwa-admin')}>
                  Redakcja sołectw
                </button>
              )}
              <button onClick={() => setActiveTab('firma')} aria-current={activeTab === 'firma' ? 'page' : undefined} className={tabClass('firma')}>
                Moja firma
              </button>
              <button onClick={() => setActiveTab('polecaj')} aria-current={activeTab === 'polecaj' ? 'page' : undefined} className={tabClass('polecaj')}>
                Polecaj
                <span className={`tabular ml-auto text-[13px] font-extrabold ${activeTab === 'polecaj' ? 'opacity-70' : 'text-tv-muted'}`}>+14 dni</span>
              </button>
              {/* Wyloguj zamyka siatkę — przy nieparzystej liczbie pozycji wypełnia wiersz */}
              <button
                onClick={handleLogout}
                className="flex min-h-[44px] w-full items-center gap-2 bg-tv-panel px-3 text-left text-[15px] font-semibold text-tv-muted transition-colors hover:bg-tv-panel2 hover:text-white"
              >
                <LogOut size={17} aria-hidden />
                Wyloguj się
              </button>
            </nav>
          </div>
        </div>

        {/* Content */}
        <div className={`min-w-0 ${activeTab === 'subscription' ? 'lg:col-span-4' : 'lg:col-span-3'}`}>
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="space-y-6 lg:space-y-8">
            <Section title="Dane profilu">
              <form onSubmit={handleProfileSubmit} className="space-y-5">

                {/* Avatar Upload */}
                <div className="flex items-center gap-4">
                  {profileData.avatarUrl ? (
                    <img
                      src={profileData.avatarUrl}
                      alt="Avatar preview"
                      className="h-20 w-20 shrink-0 object-cover"
                    />
                  ) : (
                    <div className="font-cond flex h-20 w-20 shrink-0 items-center justify-center bg-tv-panel2 text-[28px] font-extrabold text-white">
                      {initials}
                    </div>
                  )}
                  <div>
                    <label className="inline-flex min-h-[44px] cursor-pointer items-center gap-2 bg-tv-paper px-4 text-[15px] font-bold text-tv-ink transition-colors hover:bg-white">
                      <Camera size={17} aria-hidden />
                      Zmień zdjęcie profilowe
                      <input type="file" className="sr-only" accept="image/*" onChange={handleAvatarChange} />
                    </label>
                    <p className="mt-1.5 text-[13px] text-tv-muted">JPG, PNG lub GIF. Max 2MB.</p>
                  </div>
                </div>

                <div>
                  <label htmlFor="profile-name" className={LABEL}>
                    Imię i nazwisko
                  </label>
                  <input
                    id="profile-name"
                    type="text"
                    value={profileData.full_name}
                    onChange={(e) =>
                      setProfileData((p) => ({ ...p, full_name: e.target.value }))
                    }
                    className={INPUT}
                    disabled={isLoading}
                  />
                </div>

                <div>
                  <label htmlFor="profile-email" className={LABEL}>
                    Email
                  </label>
                  <input
                    id="profile-email"
                    type="email"
                    value={user.email}
                    disabled
                    className={`${INPUT} bg-tv-panel text-tv-muted disabled:opacity-100`}
                  />
                  <p className={HINT}>
                    Email nie może być zmieniony
                  </p>
                </div>

                <div>
                  <label htmlFor="profile-location" className={LABEL}>
                    Twoja miejscowość
                  </label>
                  <Select
                    id="profile-location"
                    value={profileData.location}
                    onChange={(e) =>
                      setProfileData((p) => ({ ...p, location: e.target.value }))
                    }
                    disabled={isLoading}
                  >
                    {AVAILABLE_LOCATIONS.map((loc) => (
                      <option key={loc} value={loc}>
                        {loc}
                      </option>
                    ))}
                  </Select>
                  {/* 11.10.2026: to jedyne miejsce STAŁEJ zmiany wsi — główka pulpitu
                      przełącza tylko podgląd na czas wizyty (`useMyVillage`). Zdanie
                      mówi tyle, ile robi kod: pulpit startuje od wsi z konta, wywóz
                      i wieczorny push o odpadach czytają `users.location`
                      (`waste_policy`), a alerty o awariach mają wieś zapisaną na
                      SUBSKRYPCJI push, nie na koncie */}
                  <p className={HINT}>
                    Od tej miejscowości startuje pulpit, terminy wywozu odpadów i wieczorne
                    przypomnienie o wywozie; alerty o awariach mają osobny wybór wsi przy zgodzie
                    na powiadomienia.
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className={PRIMARY}
                >
                  {isLoading ? 'Zapisywanie...' : 'Zapisz zmiany'}
                </button>
              </form>
            </Section>

            {/* Prywatność i dane (RODO art. 15/17/20) */}
            <Section title="Prywatność i dane" tone="seam">
              <p className="text-[15px] leading-snug text-[#d7dbe8]">
                Masz prawo do kopii swoich danych oraz do usunięcia konta (RODO).
                Szczegóły w Polityce prywatności.
              </p>

              <div className="-mx-5 -mb-5 mt-5 grid gap-px border-t border-tv-seam bg-tv-seam sm:-mx-6 sm:-mb-6">
                <div className="flex flex-col gap-3 bg-tv-panel px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                  <div>
                    <p className="text-[16px] font-semibold text-white">Pobierz moje dane</p>
                    <p className="text-[14px] leading-snug text-tv-muted">
                      Kopia wszystkich Twoich danych w formacie JSON (profil, zgody, rozmowy z AI, subskrypcje)
                    </p>
                  </div>
                  <button
                    onClick={handleExportData}
                    disabled={exporting}
                    className={`${SECONDARY} shrink-0`}
                  >
                    {exporting ? 'Przygotowuję...' : 'Pobierz (JSON)'}
                  </button>
                </div>

                <div className="flex flex-col gap-3 bg-tv-panel px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                  <div>
                    <p className="text-[16px] font-semibold text-white">Usuń konto</p>
                    <p className="text-[14px] leading-snug text-tv-muted">
                      Trwale usuwa konto, rozmowy z AI, powiadomienia i newsletter. Tej operacji nie można cofnąć.
                    </p>
                  </div>
                  <button
                    onClick={() => { setDeleteConfirmText(''); setDeleteModalOpen(true); }}
                    className="min-h-[44px] shrink-0 whitespace-nowrap border-2 border-tv-seam px-4 text-[15px] font-bold text-tv-paper transition-colors hover:border-tv-paper hover:text-white"
                  >
                    Usuń konto
                  </button>
                </div>
              </div>
            </Section>

            {/* Modal potwierdzenia usunięcia konta — płaski panel, tło bez rozmycia.
                Potwierdzenie na żółci: to ostrzeżenie, nie awaria (czerwień = awaria) */}
            {deleteModalOpen && (
              <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/70 p-4">
                <div role="dialog" aria-modal="true" aria-labelledby="delete-title" className="w-full max-w-md border border-t-2 border-tv-seam border-t-tv-blue bg-tv-panel p-5 sm:p-6">
                  <h3 id="delete-title" className="font-cond mb-3 text-[22px] font-extrabold leading-snug text-white">Usunąć konto na zawsze?</h3>
                  <p className="mb-4 text-[15px] leading-relaxed text-[#d7dbe8]">
                    Usuniemy Twoje konto, rozmowy z AI, subskrypcje powiadomień i newsletter.
                    Historia płatności zostanie zanonimizowana (obowiązek podatkowy).
                    <strong className="text-white"> Tej operacji nie można cofnąć.</strong>
                  </p>
                  <label htmlFor="delete-confirm" className={LABEL}>
                    Wpisz <span className="font-cond font-extrabold text-tv-yellow">USUŃ</span> aby potwierdzić
                  </label>
                  <input
                    id="delete-confirm"
                    type="text"
                    value={deleteConfirmText}
                    onChange={(e) => setDeleteConfirmText(e.target.value)}
                    className={`${INPUT} mb-4`}
                    placeholder="USUŃ"
                    autoFocus
                  />
                  <div className="flex flex-wrap justify-end gap-3">
                    <button
                      onClick={() => setDeleteModalOpen(false)}
                      disabled={deleting}
                      className={SECONDARY}
                    >
                      Anuluj
                    </button>
                    <button
                      onClick={handleDeleteAccount}
                      disabled={deleteConfirmText !== 'USUŃ' || deleting}
                      className="font-cond min-h-[44px] bg-tv-yellow px-4 text-[16px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-[#ffe27a] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {deleting ? 'Usuwanie...' : 'Usuń konto na zawsze'}
                    </button>
                  </div>
                </div>
              </div>
            )}
            </div>
          )}

          {/* Password Tab */}
          {activeTab === 'password' && (
            <Section title="Zmiana hasła">
              <form onSubmit={handlePasswordSubmit} className="space-y-5">
                <div>
                  <label htmlFor="pw-current" className={LABEL}>
                    Aktualne hasło
                  </label>
                  <input
                    id="pw-current"
                    type="password"
                    autoComplete="current-password"
                    value={passwordData.currentPassword}
                    onChange={(e) =>
                      setPasswordData((p) => ({ ...p, currentPassword: e.target.value }))
                    }
                    className={INPUT}
                    disabled={isLoading}
                  />
                </div>

                <div>
                  <label htmlFor="pw-new" className={LABEL}>
                    Nowe hasło
                  </label>
                  <input
                    id="pw-new"
                    type="password"
                    autoComplete="new-password"
                    value={passwordData.newPassword}
                    onChange={(e) =>
                      setPasswordData((p) => ({ ...p, newPassword: e.target.value }))
                    }
                    className={INPUT}
                    disabled={isLoading}
                  />
                  <p className={HINT}>
                    Min. 8 znaków, wielka litera i cyfra
                  </p>
                </div>

                <div>
                  <label htmlFor="pw-confirm" className={LABEL}>
                    Potwierdź nowe hasło
                  </label>
                  <input
                    id="pw-confirm"
                    type="password"
                    autoComplete="new-password"
                    value={passwordData.confirmPassword}
                    onChange={(e) =>
                      setPasswordData((p) => ({ ...p, confirmPassword: e.target.value }))
                    }
                    className={INPUT}
                    disabled={isLoading}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className={PRIMARY}
                >
                  {isLoading ? 'Zmieniam...' : 'Zmień hasło'}
                </button>
              </form>
            </Section>
          )}

          {/* Subscription Tab */}
          {activeTab === 'subscription' && (
            <Section
              title="Subskrypcja"
              aside={<span className="flex items-center gap-2 text-[14px] text-tv-muted">Aktualny plan: {getTierBadge(user.tier as UserTier)}</span>}
            >
              {/* Wymóg konsumencki: zamówienie z obowiązkiem zapłaty wymaga akceptacji regulaminu */}
              <label className="mb-6 flex min-h-[44px] cursor-pointer items-start gap-3 border border-tv-seam bg-tv-ink px-4 py-3">
                <SquareCheck
                  checked={acceptTerms}
                  onChange={setAcceptTerms}
                />
                <span className="text-[15px] leading-relaxed text-[#d7dbe8]">
                  Akceptuję{' '}
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); onNavigate('terms'); }}
                    className={LINK}
                  >
                    Regulamin
                  </button>{' '}
                  i przyjmuję do wiadomości, że wybór planu oznacza zamówienie z obowiązkiem zapłaty.
                  Zasady przetwarzania danych opisuje{' '}
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); onNavigate('privacy'); }}
                    className={LINK}
                  >
                    Polityka prywatności
                  </button>.
                </span>
              </label>

              <PricingCards
                currentTier={user.tier}
                onSelect={async (tierKey, frequency) => {
                  const token = getAccessToken();
                  if (!token) {
                    alert('Musisz być zalogowany, aby wybrać plan.');
                    return;
                  }
                  if (!acceptTerms) {
                    setLocalError('Zaznacz akceptację Regulaminu, aby przejść do płatności.');
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                    return;
                  }
                  try {
                    const period = frequency;
                    const res = await fetch(`${API_BASE_URL}/payments/create-transaction`, {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json',
                        Authorization: `Bearer ${token}`,
                      },
                      body: JSON.stringify({ tier: tierKey, period, accept_terms: true }),
                    });
                    if (!res.ok) {
                      const err = await res.json().catch(() => ({}));
                      // 503 = bramka jeszcze nieaktywna; komunikat z backendu podaje drogę do zakupu
                      setLocalError(err.detail || 'Błąd podczas tworzenia płatności.');
                      window.scrollTo({ top: 0, behavior: 'smooth' });
                      return;
                    }
                    const data = await res.json();
                    window.location.href = data.redirect_url;
                  } catch {
                    alert('Nie udało się połączyć z serwisem płatności.');
                  }
                }}
              />
            </Section>
          )}

          {/* Preferences Tab */}
          {activeTab === 'preferences' && (
            <div className="space-y-6 lg:space-y-8">
              {/* Newsletter */}
              <NewsletterPrefs isPremium={isPremium} apiBase={API_BASE_URL} />

              {/* Push Notifications — dla WSZYSTKICH.
                  Alerty o awariach i zagrożeniach nigdy nie trafiają za paywall. */}
              <Section title="Powiadomienia push">
                  <p className="mb-5 text-[15px] leading-snug text-[#d7dbe8]">
                    Alerty pilne w czasie rzeczywistym — nie pokrywają się z newsletterem.
                  </p>

                  {!pushSupported ? (
                    <Notice>Twoja przeglądarka nie obsługuje powiadomień push.</Notice>
                  ) : pushStatus === 'denied' ? (
                    <Notice tone="warn">
                      Powiadomienia zablokowane w ustawieniach przeglądarki. Zmień pozwolenia ręcznie.
                    </Notice>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-4 border border-tv-seam bg-tv-ink px-4 py-3">
                        <div className="flex-1">
                          <p id="push-alerts-label" className="text-[16px] font-semibold text-white">Alerty o awariach i zagrożeniach</p>
                          <p className="mt-0.5 text-[14px] text-[#d7dbe8]">
                            Prąd · Woda · Pożary · Wypadki · Smog · Mróz &lt; −5°C
                          </p>
                          <p className="mt-1 text-[13px] text-tv-muted">
                            Tylko zdarzenia z gminy Rybno — sąsiednie gminy pomijamy.
                          </p>
                        </div>
                        {/* Przełącznik kanciasty, cel dotyku 44 px wokół toru 48×28 */}
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
                          className="group inline-flex h-11 shrink-0 cursor-pointer items-center disabled:cursor-not-allowed disabled:opacity-50"
                          role="switch"
                          aria-checked={pushSubscribed}
                          aria-labelledby="push-alerts-label"
                        >
                          <span className={`relative inline-flex h-7 w-12 items-center border-2 transition-colors ${
                            pushSubscribed ? 'border-tv-blue bg-tv-blue' : 'border-tv-muted bg-tv-ink'
                          }`}>
                            <span className={`inline-block h-5 w-5 transition-transform duration-200 ${
                              pushSubscribed ? 'translate-x-[22px] bg-white' : 'translate-x-0.5 bg-tv-muted'
                            }`} />
                          </span>
                        </button>
                      </div>
                      {pushSubscribed && (
                        <p className="flex items-center gap-2 text-[14px] text-tv-muted">
                          <Check size={16} className="shrink-0 text-tv-green" aria-hidden />
                          Alerty aktywne — otrzymasz wszystkie pilne powiadomienia.
                        </p>
                      )}
                    </div>
                  )}
              </Section>

              {/* Account info */}
              <Section title="Informacje o koncie" tone="seam">
                <dl className="space-y-3 text-[15px]">
                  <div className="flex justify-between gap-4">
                    <dt className="text-tv-muted">Data rejestracji</dt>
                    <dd className="tabular font-medium text-white">
                      {new Date(user.created_at).toLocaleDateString('pl-PL')}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-tv-muted">Ostatnie logowanie</dt>
                    <dd className="tabular text-right font-medium text-white">
                      {user.last_login
                        ? new Date(user.last_login).toLocaleString('pl-PL')
                        : '-'}
                    </dd>
                  </div>
                  {/* Wiersz "Email zweryfikowany" ukryty do czasu wdrożenia
                      pełnej weryfikacji e-mail (mail z linkiem + endpoint /verify).
                      Obecnie email_verified nigdy nie jest ustawiane, więc pole
                      pokazywało "Nie" wszystkim. Przywrócić po implementacji. */}
                </dl>
              </Section>
            </div>
          )}
          {/* Sołectwo — ogłoszenia sołtysa (zdjęcie pisma → redakcja → strona) */}
          {activeTab === 'solectwo' && (postingRole
            ? <SolectwoPanel role={postingRole} />
            : <Notice>
                To konto nie ma roli sołtysa. Link z zaproszeniem otrzymasz od redakcji RybnoLive.
              </Notice>)}
          {/* Redakcja sołectw — moderacja, zaproszenia, role (tylko admin) */}
          {activeTab === 'solectwa-admin' && user.is_admin && <SolectwaAdminPanel />}
          {/* Moja firma — wizytówki przypisane do tego konta */}
          {activeTab === 'firma' && (
            <MyBusinessPanel
              onGoToCatalog={() => onNavigate('business')}
              onGoToPricing={() => onNavigate('premium')}
            />
          )}
          {/* Polecaj Tab */}
          {activeTab === 'polecaj' && (
            <div className="space-y-6 lg:space-y-8">
              <Section title="Program Polecający">
                <p className="mb-5 text-[15px] leading-snug text-[#d7dbe8]">Zaproś znajomych — oboje dostaniecie <span className="font-semibold text-white">+14 dni Premium</span> za każde polecenie.</p>

                {referralData ? (
                  <div className="space-y-4">
                    {/* Code */}
                    <div className="flex flex-col gap-4 border border-tv-seam bg-tv-ink p-4 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="mb-1 text-[13px] text-tv-muted">Twój kod polecający</p>
                        <p className="font-cond tabular text-[28px] font-extrabold tracking-widest text-white">{referralData.referral_code.toUpperCase()}</p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <button
                          onClick={copyReferralLink}
                          className={`${SECONDARY} inline-flex items-center gap-1.5`}
                        >
                          {referralCopied ? <><Check size={16} className="text-tv-green" aria-hidden /> Skopiowano</> : 'Kopiuj link'}
                        </button>
                        <button
                          onClick={shareReferralLink}
                          className="font-cond min-h-[44px] bg-tv-blue px-4 text-[16px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff]"
                        >
                          Udostępnij
                        </button>
                      </div>
                    </div>

                    {/* Link preview */}
                    <div className="border border-tv-seam px-4 py-3">
                      <p className="mb-1 text-[13px] text-tv-muted">Link do zaproszenia</p>
                      <p className="break-all text-[14px] text-tv-bluesoft">{referralData.referral_link}</p>
                    </div>

                    {/* Stats */}
                    <div className="grid grid-cols-2 gap-px border border-tv-seam bg-tv-seam">
                      <div className="bg-tv-ink p-4">
                        <p className="font-cond tabular text-[30px] font-extrabold leading-none text-white">{referralData.referrals_count}</p>
                        <p className="mt-1.5 text-[13px] text-tv-muted">Zaproszonych osób</p>
                      </div>
                      <div className="bg-tv-ink p-4">
                        <p className="font-cond tabular text-[30px] font-extrabold leading-none text-white">{referralData.referrals_count * 14}</p>
                        <p className="mt-1.5 text-[13px] text-tv-muted">Dni Premium zdobytych</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <Skeleton className="h-32" />
                )}
              </Section>

              {/* How it works — numery zostają: kolejność kroków jest tu treścią */}
              <Section title="Jak to działa?" tone="seam">
                <ol className="space-y-4">
                  {[
                    ['1', 'Udostępnij swój link znajomym z Gminy Rybno'],
                    ['2', 'Znajomy rejestruje się przez Twój link'],
                    ['3', 'Oboje otrzymujecie +14 dni Premium — automatycznie'],
                  ].map(([n, text]) => (
                    <li key={n} className="flex items-start gap-4">
                      <span className="font-cond tabular flex h-7 w-7 shrink-0 items-center justify-center bg-tv-panel2 text-[15px] font-extrabold text-white">{n}</span>
                      <span className="pt-0.5 text-[15px] text-[#d7dbe8]">{text}</span>
                    </li>
                  ))}
                </ol>
              </Section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
