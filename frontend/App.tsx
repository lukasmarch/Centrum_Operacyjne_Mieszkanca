import React, { useState, useCallback, useEffect, lazy, Suspense } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Dashboard from './components/Dashboard';
import NewsFeed from './components/NewsFeed';
import EventsFeed from './components/EventsFeed';
import { AppSection, TabId } from './types';
import { DataCacheProvider } from './src/context/DataCacheContext';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import LoginPage from './src/pages/LoginPage';
import RegisterPage from './src/pages/RegisterPage';
import BottomTabBar from './components/navigation/BottomTabBar';
import { PWAInstallPrompt } from './components/PWAInstallPrompt';
import CookieConsent from './components/CookieConsent';
import PaymentReturnBanner from './components/PaymentReturnBanner';
import PricingCards from './components/PricingCards';
import SubNavBar from './components/navigation/SubNavBar';
import TopBar from './components/navigation/TopBar';
import { BeamsBackground } from './components/ui/beams-background';

// Lazy-loaded pages — pobierane dopiero przy pierwszym wejściu
const ProfilePage  = lazy(() => import('./src/pages/ProfilePage'));
const GUSPage      = lazy(() => import('./src/pages/GUSPage'));
const WeatherPage  = lazy(() => import('./src/pages/WeatherPage'));
const BusinessPage = lazy(() => import('./src/pages/BusinessPage'));
const ReportsPage  = lazy(() => import('./src/pages/ReportsPage'));
const AssistantPage = lazy(() => import('./src/pages/AssistantPage'));
const TermsPage        = lazy(() => import('./src/pages/TermsPage'));
const PrivacyPage      = lazy(() => import('./src/pages/PrivacyPage'));
const CookiePolicyPage = lazy(() => import('./src/pages/CookiePolicyPage'));

const MIASTO_ITEMS = [
    { id: 'news', label: 'Wiadomości' },
    { id: 'events', label: 'Wydarzenia' },
    { id: 'weather', label: 'Pogoda' },
];

// Zakładka "Firmy": katalog wizytówek jako front, Statystyki GUS dostępne
// przyciskiem na stronie Firm (sekcja 'stats' bez własnej pozycji w nawigacji)

// Map sections to their parent tab
const SECTION_TO_TAB: Record<AppSection, TabId> = {
    dashboard: 'home',
    assistant: 'assistant',
    news: 'miasto',
    events: 'miasto',
    weather: 'miasto',
    reports: 'zgloszenia',
    stats: 'dane',
    business: 'dane',
    premium: 'home',
    profile: 'home',
    login: 'home',
    register: 'home',
    terms: 'home',
    privacy: 'home',
    cookies: 'home',
};

// Default section for each tab
const TAB_DEFAULT_SECTION: Record<TabId, AppSection> = {
    home: 'dashboard',
    assistant: 'assistant',
    miasto: 'news',
    dane: 'business',
    zgloszenia: 'reports',
};

const AppContent: React.FC = () => {
    const [activeSection, setActiveSection] = useState<AppSection>('dashboard');
    const [activeTab, setActiveTab] = useState<TabId>('home');
    const [initialQuery, setInitialQuery] = useState<string>('');
    const { user, isAuthenticated, isLoading, logout } = useAuth();

    const [profileInitialTab, setProfileInitialTab] = useState<'profile' | 'password' | 'preferences' | 'subscription' | undefined>(undefined);

    const handleNavigate = useCallback((section: AppSection | 'logout' | 'preferences' | 'subscription') => {
        if (section === 'logout') {
            logout();
            setActiveSection('dashboard');
            setActiveTab('home');
        } else if (section === 'preferences') {
            setProfileInitialTab('preferences');
            setActiveSection('profile');
            setActiveTab(SECTION_TO_TAB['profile']);
        } else if (section === 'subscription') {
            setProfileInitialTab('subscription');
            setActiveSection('profile');
            setActiveTab(SECTION_TO_TAB['profile']);
        } else {
            setProfileInitialTab(undefined);
            setActiveSection(section);
            setActiveTab(SECTION_TO_TAB[section]);
        }
    }, [logout]);

    const handleTabChange = useCallback((tab: TabId) => {
        setActiveTab(tab);
        setActiveSection(TAB_DEFAULT_SECTION[tab]);
    }, []);

    // Listen for GUSTierGate subscription navigation events
    useEffect(() => {
        const handleSubscriptionNav = () => handleNavigate('subscription');
        window.addEventListener('navigate-to-subscription', handleSubscriptionNav);
        return () => window.removeEventListener('navigate-to-subscription', handleSubscriptionNav);
    }, [handleNavigate]);

    const handleSubNavChange = useCallback((id: string) => {
        setActiveSection(id as AppSection);
    }, []);

    const renderContent = () => {
        // Auth pages
        if (activeSection === 'login') {
            return <LoginPage onNavigate={handleNavigate} />;
        }
        if (activeSection === 'register') {
            return <RegisterPage onNavigate={handleNavigate} />;
        }

        // Profile page (requires login)
        if (activeSection === 'profile') {
            if (!isAuthenticated) {
                handleNavigate('login');
                return null;
            }
            return <ProfilePage onNavigate={handleNavigate} initialTab={profileInitialTab} />;
        }

        switch (activeSection) {
            case 'dashboard':
                return <Dashboard onNavigate={handleNavigate} onQuerySubmit={setInitialQuery} />;
            case 'assistant':
                return <AssistantPage initialQuery={initialQuery} onNavigate={handleNavigate} />;
            case 'news':
                return <NewsFeed />;
            case 'events':
                return <EventsFeed />;
            case 'weather':
                return <WeatherPage />;
            case 'stats':
                return (
                    <div>
                        <div className="max-w-7xl mx-auto px-4 pt-4">
                            <button
                                onClick={() => handleNavigate('business')}
                                className="text-sm text-neutral-400 hover:text-neutral-200 font-medium transition-colors"
                            >
                                ← Wróć do Firm
                            </button>
                        </div>
                        <GUSPage />
                    </div>
                );
            case 'business':
                return <BusinessPage onNavigate={handleNavigate} />;
            case 'reports':
                return <ReportsPage onNavigate={handleNavigate} />;
            case 'terms':
                return <TermsPage onNavigate={handleNavigate} />;
            case 'privacy':
                return <PrivacyPage onNavigate={handleNavigate} />;
            case 'cookies':
                return <CookiePolicyPage onNavigate={handleNavigate} />;
            case 'premium':
                return (
                    <div className="max-w-4xl mx-auto py-12">
                        <div className="text-center mb-12">
                            <h2 className="text-4xl font-black mb-4 text-gradient-saas">Wybierz swój plan</h2>
                            <p className="text-neutral-500 text-lg">Wspieraj lokalne dziennikarstwo i zyskaj dostęp do ekstra funkcji.</p>
                        </div>
                        <PricingCards
                            currentTier={user?.tier || 'free'}
                            onSelect={() => {
                                // Checkout (z wymaganą akceptacją regulaminu) mieszka w Profil → Subskrypcja
                                handleNavigate(isAuthenticated ? 'subscription' : 'register');
                            }}
                        />
                    </div>
                );
            default:
                return (
                    <div className="p-20 text-center flex flex-col items-center justify-center">
                        <span className="text-6xl mb-4">🚧</span>
                        <h3 className="text-2xl font-bold">Sekcja w budowie</h3>
                        <p className="text-neutral-500 max-w-sm">Ten moduł jest aktualnie opracowywany przez nasz zespół AI i developerów.</p>
                        <button onClick={() => handleNavigate('dashboard')} className="mt-6 text-blue-500 font-bold">Wróć do kokpitu</button>
                    </div>
                );
        }
    };

    // Loading state
    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-black">
                <div className="text-center">
                    <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-violet-600 rounded-2xl flex items-center justify-center font-bold text-3xl text-white mx-auto mb-4 animate-pulse shadow-lg shadow-blue-500/30">
                        R
                    </div>
                    <p className="text-neutral-500">Ładowanie...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen text-white selection:bg-blue-500/30 overflow-x-hidden" style={{ background: '#05080f' }}>
            {/* Global BeamsBackground — fixed full-page, shared with hero */}
            <BeamsBackground intensity="medium" className="fixed inset-0 pointer-events-none" />
            {/* Extra depth: dark radial overlay at centre-bottom */}
            <div className="fixed inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_100%,rgba(37,99,239,0.06),transparent)] pointer-events-none" />

            {/* Top Bar */}
            <TopBar
                user={user}
                isAuthenticated={isAuthenticated}
                onNavigate={handleNavigate}
            />

            {/* Sub Navigation for Miasto / Dane tabs */}
            {activeTab === 'miasto' && (
                <SubNavBar
                    items={MIASTO_ITEMS}
                    activeItem={activeSection}
                    onItemChange={handleSubNavChange}
                />
            )}

            {/* Dynamic Content */}
            <main className="pb-24 relative z-10">
                {/* AssistantPage always mounted — preserves chat state between tab switches */}
                <div style={{ display: activeSection === 'assistant' ? 'block' : 'none' }}>
                    <Suspense fallback={null}>
                        <AssistantPage
                            initialQuery={initialQuery}
                            onNavigate={handleNavigate}
                            onInitialQuerySent={() => setInitialQuery('')}
                        />
                    </Suspense>
                </div>

                {/* All other sections with animation */}
                {activeSection !== 'assistant' && (
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={activeSection}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -8 }}
                            transition={{ duration: 0.25, ease: 'easeOut' }}
                        >
                            <div className="max-w-7xl mx-auto p-4 md:p-8">
                                <Suspense fallback={null}>
                                    {renderContent()}
                                </Suspense>
                            </div>
                        </motion.div>
                    </AnimatePresence>
                )}
            </main>

            {/* Footer */}
            {activeSection !== 'assistant' && <footer className="max-w-7xl mx-auto px-8 py-10 mb-20 border-t border-white/5 text-neutral-600 text-xs flex flex-col md:flex-row justify-between items-center gap-4 relative z-10">
                <div className="flex flex-col md:flex-row items-center gap-2 md:gap-6">
                    <p className="font-medium">© 2026 Rybno Live · Ai_lumargo</p>
                    <div className="flex gap-4">
                        <button onClick={() => handleNavigate('privacy')} className="hover:text-blue-400 transition-colors">Prywatność</button>
                        <button onClick={() => handleNavigate('terms')} className="hover:text-blue-400 transition-colors">Regulamin</button>
                        <button onClick={() => handleNavigate('cookies')} className="hover:text-blue-400 transition-colors">Cookies</button>
                    </div>
                </div>
                <div className="flex gap-4 font-mono opacity-50">
                    <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Rybno-1</span>
                    <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> API: v2.4</span>
                </div>
            </footer>}

            {/* Status płatności po powrocie z Przelewy24 (/payment/success?session=...) */}
            <PaymentReturnBanner />

            {/* PWA install prompt — shown after 3rd visit */}
            <PWAInstallPrompt />

            {/* Baner zgody cookies (PKE) — pokazywany do czasu podjęcia decyzji */}
            <CookieConsent onNavigate={handleNavigate} />

            {/* Bottom Tab Bar */}
            <BottomTabBar
                activeTab={activeTab}
                onTabChange={handleTabChange}
                isAuthenticated={isAuthenticated}
            />
        </div>
    );
};

const App: React.FC = () => {
    return (
        <AuthProvider>
            <DataCacheProvider>
                <AppContent />
            </DataCacheProvider>
        </AuthProvider>
    );
};

export default App;
