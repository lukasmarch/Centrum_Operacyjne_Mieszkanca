import React, { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
// Uwaga: components/Dashboard.tsx (bento-panel) NIE jest już nigdzie routowany.
// Zostaje w repo jako magazyn kafli, których nie ma jeszcze gdzie indziej
// (ruch drogowy, kino, apteka dyżurna, monitoring) — do przeniesienia na
// strony szczegółowe, potem plik można skasować.
import NewsFeed from './components/NewsFeed';
import EventsFeed from './components/EventsFeed';
import { AppSection, TabId } from './types';
import { applySeo } from './src/seo';
import SimpleHomePage from './src/pages/SimpleHomePage';
import WastePage from './src/pages/WastePage';
import BusPage from './src/pages/BusPage';
import { DataCacheProvider } from './src/context/DataCacheContext';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import LoginPage from './src/pages/LoginPage';
import RegisterPage from './src/pages/RegisterPage';
import BottomTabBar from './components/navigation/BottomTabBar';
import { PWAInstallPrompt } from './components/PWAInstallPrompt';
import CookieConsent from './components/CookieConsent';
import PaymentReturnBanner from './components/PaymentReturnBanner';
import PricingCards, { Frequency } from './components/PricingCards';
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
const CheckoutPage     = lazy(() => import('./src/pages/CheckoutPage'));

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
    waste: 'miasto',
    bus: 'miasto',
    reports: 'zgloszenia',
    stats: 'dane',
    business: 'dane',
    premium: 'home',
    checkout: 'home',
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

// Sekcje z własnym adresem URL — muszą być osiągalne bezpośrednim linkiem
// (weryfikacja Przelewy24 wymaga stałego adresu regulaminu i cennika).
// Pozostałe sekcje żyją pod "/" jak dotąd.
export const SECTION_TO_PATH: Partial<Record<AppSection, string>> = {
    terms: '/regulamin',
    privacy: '/polityka-prywatnosci',
    cookies: '/polityka-cookies',
    premium: '/cennik',
    checkout: '/zamowienie',
    // Newsletter linkuje do zgłoszeń — bez własnej ścieżki mail lądował na dashboardzie
    reports: '/zgloszenia',
    // Sekcje treściowe z własnym adresem — warunek indeksowania w Google:
    // bez ścieżki nie ma czego wpisać do sitemapy ani do canonical.
    // Lustro tej listy trzyma backend/src/api/endpoints/seo.py (sitemap.xml).
    news: '/wiadomosci',
    events: '/wydarzenia',
    weather: '/pogoda',
    waste: '/harmonogram-odpadow',
    bus: '/autobus',
    stats: '/statystyki',
    business: '/firmy',
    assistant: '/asystent',
};

const PATH_TO_SECTION: Record<string, AppSection> = Object.entries(SECTION_TO_PATH)
    .reduce((acc, [section, path]) => ({ ...acc, [path]: section as AppSection }), {});

const sectionFromPath = (): AppSection =>
    PATH_TO_SECTION[window.location.pathname.replace(/\/+$/, '')] ?? 'dashboard';

/**
 * Nieznany adres pokazuje stronę główną, więc musi też mieć jej adres — inaczej
 * stary link (np. do wycofanego `/panel`) zostaje w pasku i w indeksie Google
 * jako osobna strona z tą samą treścią. Wyjątek: powrót z Przelewy24, którego
 * ścieżkę czyta PaymentReturnBanner.
 */
const normalizeUnknownPath = () => {
    const path = window.location.pathname.replace(/\/+$/, '');
    if (!path || path === '/payment/success' || PATH_TO_SECTION[path]) return;
    window.history.replaceState({}, '', `/${window.location.search}`);
};

// Wybrany plan żyje w adresie (/zamowienie?plan=premium&okres=yearly), żeby zamówienie
// przetrwało odświeżenie strony i drogę przez rejestrację konta
type CheckoutSelection = { tier: string; frequency: Frequency };

const checkoutFromUrl = (): CheckoutSelection | null => {
    const params = new URLSearchParams(window.location.search);
    const tier = params.get('plan');
    if (tier !== 'premium' && tier !== 'business') return null;
    return { tier, frequency: params.get('okres') === 'yearly' ? 'yearly' : 'monthly' };
};

const AppContent: React.FC = () => {
    const [activeSection, setActiveSection] = useState<AppSection>(() => {
        normalizeUnknownPath();
        return sectionFromPath();
    });
    const [activeTab, setActiveTab] = useState<TabId>(() => SECTION_TO_TAB[sectionFromPath()]);
    const [initialQuery, setInitialQuery] = useState<string>('');
    const { user, isAuthenticated, isLoading, logout } = useAuth();

    const [profileInitialTab, setProfileInitialTab] = useState<'profile' | 'password' | 'preferences' | 'subscription' | undefined>(undefined);
    const [checkoutSelection, setCheckoutSelection] = useState<CheckoutSelection | null>(checkoutFromUrl);

    // Adres w pasku przeglądarki podąża za sekcją (tylko dla sekcji z SECTION_TO_PATH)
    const syncUrl = useCallback((section: AppSection, selection?: CheckoutSelection | null) => {
        const path = SECTION_TO_PATH[section] ?? '/';
        const sel = selection !== undefined ? selection : checkoutSelection;
        const url = section === 'checkout' && sel
            ? `${path}?plan=${sel.tier}&okres=${sel.frequency}`
            : path;
        if (window.location.pathname + window.location.search !== url) {
            window.history.pushState({}, '', url);
        }
    }, [checkoutSelection]);

    const handleNavigate = useCallback((section: AppSection | 'logout' | 'preferences' | 'subscription') => {
        if (section === 'logout') {
            logout();
            setActiveSection('dashboard');
            setActiveTab('home');
            syncUrl('dashboard');
        } else if (section === 'preferences') {
            setProfileInitialTab('preferences');
            setActiveSection('profile');
            setActiveTab(SECTION_TO_TAB['profile']);
            syncUrl('profile');
        } else if (section === 'subscription') {
            setProfileInitialTab('subscription');
            setActiveSection('profile');
            setActiveTab(SECTION_TO_TAB['profile']);
            syncUrl('profile');
        } else {
            setProfileInitialTab(undefined);
            setActiveSection(section);
            setActiveTab(SECTION_TO_TAB[section]);
            syncUrl(section);
        }
    }, [logout, syncUrl]);

    // Wybór planu w cenniku → podsumowanie zamówienia (dostępne bez konta)
    const startCheckout = useCallback((tier: string, frequency: Frequency) => {
        if (tier !== 'premium' && tier !== 'business') return;
        const selection = { tier, frequency };
        setCheckoutSelection(selection);
        setActiveSection('checkout');
        setActiveTab('home');
        syncUrl('checkout', selection);
        window.scrollTo({ top: 0 });
    }, [syncUrl]);

    // Po założeniu konta lub zalogowaniu wracamy do rozpoczętego zamówienia,
    // zamiast zostawiać kupującego na kokpicie
    const wasAuthenticated = useRef(isAuthenticated);
    useEffect(() => {
        if (isAuthenticated && !wasAuthenticated.current && checkoutSelection) {
            setActiveSection('checkout');
            setActiveTab('home');
            syncUrl('checkout', checkoutSelection);
        }
        wasAuthenticated.current = isAuthenticated;
    }, [isAuthenticated, checkoutSelection, syncUrl]);

    const handleTabChange = useCallback((tab: TabId) => {
        setActiveTab(tab);
        setActiveSection(TAB_DEFAULT_SECTION[tab]);
        syncUrl(TAB_DEFAULT_SECTION[tab]);
    }, [syncUrl]);

    // Meta per sekcja (title/description/canonical) — patrz frontend/src/seo.ts
    useEffect(() => {
        applySeo(activeSection, SECTION_TO_PATH[activeSection]);
    }, [activeSection]);

    // Przycisk wstecz/dalej w przeglądarce
    useEffect(() => {
        const handlePopState = () => {
            const section = sectionFromPath();
            setActiveSection(section);
            setActiveTab(SECTION_TO_TAB[section]);
        };
        window.addEventListener('popstate', handlePopState);
        return () => window.removeEventListener('popstate', handlePopState);
    }, []);

    // Listen for GUSTierGate subscription navigation events
    useEffect(() => {
        const handleSubscriptionNav = () => handleNavigate('subscription');
        window.addEventListener('navigate-to-subscription', handleSubscriptionNav);
        return () => window.removeEventListener('navigate-to-subscription', handleSubscriptionNav);
    }, [handleNavigate]);

    // Odnośniki stopki są prawdziwymi <a href> (widocznymi dla crawlerów i weryfikatorów),
    // ale nawigują w obrębie SPA — chyba że użytkownik otwiera w nowej karcie.
    const navLink = useCallback((section: AppSection) => (e: React.MouseEvent) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        handleNavigate(section);
        window.scrollTo({ top: 0 });
    }, [handleNavigate]);

    const handleSubNavChange = useCallback((id: string) => {
        setActiveSection(id as AppSection);
        syncUrl(id as AppSection);
    }, [syncUrl]);

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
                return <SimpleHomePage onNavigate={handleNavigate} onQuerySubmit={setInitialQuery} />;
            case 'waste':
                return <WastePage onNavigate={handleNavigate} />;
            case 'bus':
                return <BusPage onNavigate={handleNavigate} />;
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
            case 'checkout':
                return (
                    <CheckoutPage
                        tierKey={checkoutSelection?.tier ?? 'premium'}
                        frequency={checkoutSelection?.frequency ?? 'monthly'}
                        onNavigate={handleNavigate}
                    />
                );
            case 'premium':
                return (
                    <div className="max-w-4xl mx-auto py-12">
                        <div className="text-center mb-12">
                            <h2 className="text-4xl font-black mb-4 text-gradient-saas">Wybierz swój plan</h2>
                            <p className="text-neutral-500 text-lg">Wspieraj lokalne dziennikarstwo i zyskaj dostęp do ekstra funkcji.</p>
                        </div>
                        <PricingCards
                            currentTier={user?.tier || 'free'}
                            onSelect={startCheckout}
                        />

                        {/* Przebieg zakupu opisany jawnie — kupujący (i weryfikator Przelewy24)
                            musi znać kolejne kroki i warunki przed założeniem konta */}
                        <div className="mt-16 grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
                                <h3 className="text-lg font-bold mb-4">Jak kupić dostęp</h3>
                                <ol className="space-y-3 text-sm text-neutral-400">
                                    <li><span className="text-blue-400 font-bold mr-2">1.</span>Wybierz plan powyżej (Premium lub Firma lokalna) i okres rozliczeniowy — miesięczny albo roczny.</li>
                                    <li><span className="text-blue-400 font-bold mr-2">2.</span>Na stronie <strong className="text-neutral-300">Podsumowanie zamówienia</strong> sprawdź cenę i zakres planu, po czym zaakceptuj Regulamin.</li>
                                    <li><span className="text-blue-400 font-bold mr-2">3.</span>Załóż konto lub zaloguj się — dostęp do planu jest przypisany do konta w serwisie.</li>
                                    <li><span className="text-blue-400 font-bold mr-2">4.</span>Potwierdź zamówienie z obowiązkiem zapłaty i przejdź do bramki Przelewy24 — BLIK, karta lub przelew online.</li>
                                    <li><span className="text-blue-400 font-bold mr-2">5.</span>Po zaksięgowaniu płatności plan aktywuje się automatycznie, a potwierdzenie trafia na Twój e-mail.</li>
                                </ol>
                            </div>

                            <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6 text-sm text-neutral-400 space-y-4">
                                <div>
                                    <h3 className="text-lg font-bold text-white mb-2">Sprzedawca</h3>
                                    <p className="leading-relaxed">
                                        Studio Kamienia Naturalnego Lu-Mar-Go Łukasz Marchlewicz<br />
                                        Żabiny 96, 13-220 Rybno<br />
                                        NIP: 571-156-78-15<br />
                                        <a href="tel:+48501081723" className="hover:text-blue-400 transition-colors">+48 501 081 723</a>
                                        {' · '}
                                        <a href="mailto:biuro@lumargo.pl" className="hover:text-blue-400 transition-colors">biuro@lumargo.pl</a>
                                    </p>
                                </div>
                                <div>
                                    <h4 className="font-bold text-neutral-300 mb-1">Płatności i rezygnacja</h4>
                                    <p className="leading-relaxed">
                                        Płatności obsługuje PayPro S.A. (Przelewy24). Ceny są cenami brutto w złotych.
                                        Płacisz z góry za wybrany okres — subskrypcja nie odnawia się automatycznie i wygasa po jego upływie.
                                        Konsumentowi przysługuje prawo odstąpienia od umowy w terminie 14 dni (szczegóły i wzór oświadczenia w Regulaminie).
                                    </p>
                                </div>
                                <p className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
                                    <a href={SECTION_TO_PATH.terms} onClick={navLink('terms')} className="text-blue-400 hover:text-blue-300 underline underline-offset-2">Regulamin</a>
                                    <a href={SECTION_TO_PATH.privacy} onClick={navLink('privacy')} className="text-blue-400 hover:text-blue-300 underline underline-offset-2">Polityka prywatności</a>
                                    <a href={SECTION_TO_PATH.cookies} onClick={navLink('cookies')} className="text-blue-400 hover:text-blue-300 underline underline-offset-2">Polityka cookies</a>
                                </p>
                            </div>
                        </div>
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

    // `overflow-x-clip`, nie `-hidden`: `hidden` robi z korzenia kontener
    // przewijania, więc przyklejony TopBar przyklejał się do JEGO góry i uciekał
    // razem ze stroną. `clip` obcina tak samo, ale kontenera nie tworzy
    return (
        <div className="min-h-screen text-white selection:bg-blue-500/30 overflow-x-clip" style={{ background: '#05080f' }}>
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
            {activeSection !== 'assistant' && <footer className="max-w-7xl mx-auto px-8 py-10 mb-20 border-t border-white/5 text-neutral-500 text-xs relative z-10">
                {/* Blok danych sprzedawcy — identyfikacja wymagana przy sprzedaży online.
                    Nazwa firmy w brzmieniu z CEIDG (z imieniem i nazwiskiem — dla działalności
                    jednoosobowej jest ono częścią firmy) — wymóg weryfikacji Przelewy24 */}
                <div className="flex flex-col md:flex-row justify-between gap-8 mb-6">
                    <div className="leading-relaxed">
                        <p className="font-medium text-neutral-400 mb-1">© 2026 Rybno Live</p>
                        <p>Studio Kamienia Naturalnego Lu-Mar-Go Łukasz Marchlewicz</p>
                        <p>Żabiny 96</p>
                        <p>13-220 Rybno</p>
                        <p>NIP: 571-156-78-15</p>
                        <p className="mt-1">
                            <a href="tel:+48501081723" className="hover:text-blue-400 transition-colors">+48 501 081 723</a>
                        </p>
                        <p>
                            <a href="mailto:biuro@lumargo.pl" className="hover:text-blue-400 transition-colors">biuro@lumargo.pl</a>
                        </p>
                    </div>
                    <div className="flex flex-col gap-1.5 md:text-right text-neutral-400">
                        <a href={SECTION_TO_PATH.terms} onClick={navLink('terms')} className="hover:text-blue-400 transition-colors">Regulamin</a>
                        <a href={SECTION_TO_PATH.privacy} onClick={navLink('privacy')} className="hover:text-blue-400 transition-colors">Polityka prywatności</a>
                        <a href={SECTION_TO_PATH.cookies} onClick={navLink('cookies')} className="hover:text-blue-400 transition-colors">Polityka cookies</a>
                        <a href={SECTION_TO_PATH.premium} onClick={navLink('premium')} className="hover:text-blue-400 transition-colors">Cennik</a>
                    </div>
                </div>
                <div className="flex flex-col md:flex-row justify-between items-center gap-4 pt-4 border-t border-white/5">
                    <p>Płatności: Przelewy24 (BLIK, karta, przelew online)</p>
                    <div className="flex gap-4 font-mono opacity-50">
                        <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Rybno-1</span>
                        <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> API: v2.4</span>
                    </div>
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
