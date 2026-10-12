import React, { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
// Bento-panel (`components/Dashboard.tsx` i jego kafle) usunięty 11.10.2026 —
// ruch, kino i apteka żyją w kaflach pulpitu (`components/simple/*`).
import NewsFeed from './components/NewsFeed';
import EventsFeed from './components/EventsFeed';
import { AppSection, TabId } from './types';
import { applySeo } from './src/seo';
import { track } from './src/services/analytics';
import SimpleHomePage from './src/pages/SimpleHomePage';
import WastePage from './src/pages/WastePage';
import BusPage from './src/pages/BusPage';
import CinemaPage from './src/pages/CinemaPage';
import { DataCacheProvider } from './src/context/DataCacheContext';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import LoginPage from './src/pages/LoginPage';
import PasswordResetPage from './src/pages/PasswordResetPage';
import RegisterPage from './src/pages/RegisterPage';
import BottomTabBar from './components/navigation/BottomTabBar';
import { PWAInstallPrompt } from './components/PWAInstallPrompt';
import CookieConsent from './components/CookieConsent';
import PaymentReturnBanner from './components/PaymentReturnBanner';
import PricingCards, { Frequency } from './components/PricingCards';
import { PageHead } from './components/simple/tv';
import { ArrowLeft } from 'lucide-react';
import SubNavBar from './components/navigation/SubNavBar';
import TopBar from './components/navigation/TopBar';

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
const CouncilPage      = lazy(() => import('./src/pages/CouncilPage'));
const InvitePage       = lazy(() => import('./src/pages/InvitePage'));
const SolectwoPostPage = lazy(() => import('./src/pages/SolectwoPostPage'));

// Podmenu zakładki „Info". Odpady, autobus i kino dopisane razem z przebudową:
// bez nich strony powstałe 11–12.08 były osiągalne WYŁĄCZNIE z kafla na stronie
// głównej, więc ktoś, kto wszedł na `/wiadomosci` prosto z Google, nie miał jak
// do nich trafić. Pasek przewija się w poziomie, więc sześć pozycji mieści się
// na telefonie bez łamania wiersza.
const MIASTO_ITEMS = [
    { id: 'news', label: 'Wiadomości' },
    { id: 'events', label: 'Wydarzenia' },
    { id: 'council', label: 'Sesje Rady' },
    { id: 'weather', label: 'Pogoda' },
    { id: 'waste', label: 'Odpady' },
    { id: 'bus', label: 'Autobus' },
    { id: 'cinema', label: 'Kino' },
];

// Nawigacja sekcji w nagłówku na szerokim ekranie (od `lg`). Na telefonie tę rolę
// pełnią dolna belka + podmenu „Gmina”. Kolejność: pulpit, potem to, po co się
// wraca najczęściej (wiadomości, wydarzenia, odpady, autobus), urzędowe, reszta.
const TOP_NAV: { id: AppSection; label: string }[] = [
    { id: 'dashboard', label: 'Pulpit' },
    { id: 'news', label: 'Wiadomości' },
    { id: 'events', label: 'Wydarzenia' },
    { id: 'waste', label: 'Odpady' },
    { id: 'bus', label: 'Autobus' },
    { id: 'weather', label: 'Pogoda' },
    { id: 'council', label: 'Rada' },
    { id: 'cinema', label: 'Kino' },
    { id: 'business', label: 'Firmy' },
    { id: 'reports', label: 'Zgłoszenia 24' },
    { id: 'assistant', label: 'Asystent' },
];

// Zakładka "Firmy": katalog wizytówek jako front, Statystyki GUS dostępne
// przyciskiem na stronie Firm (sekcja 'stats' bez własnej pozycji w nawigacji)

// Map sections to their parent tab
const SECTION_TO_TAB: Record<AppSection, TabId> = {
    dashboard: 'home',
    assistant: 'assistant',
    news: 'miasto',
    events: 'miasto',
    council: 'miasto',
    weather: 'miasto',
    waste: 'miasto',
    bus: 'miasto',
    cinema: 'miasto',
    reports: 'zgloszenia',
    stats: 'dane',
    business: 'dane',
    premium: 'home',
    checkout: 'home',
    profile: 'home',
    login: 'home',
    register: 'home',
    'reset-password': 'home',
    terms: 'home',
    privacy: 'home',
    cookies: 'home',
    invite: 'home',
    announcement: 'miasto',
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
    council: '/sesje',
    weather: '/pogoda',
    waste: '/harmonogram-odpadow',
    bus: '/autobus',
    cinema: '/kino',
    stats: '/statystyki',
    business: '/firmy',
    assistant: '/asystent',
    // Profil ma adres nie po to, żeby go indeksować (sitemapa go nie zna —
    // patrz backend/src/api/endpoints/seo.py), tylko żeby dało się w niego
    // wysłać człowieka mailem: decyzja o wizytówce linkuje do /profil?zakladka=firma
    profile: '/profil',
    // Jak profil: adresy do wysyłania ludzi linkiem, NIE do sitemapy.
    // /zaproszenie?kod=… — link dla sołtysa po rozmowie telefonicznej;
    // /ogloszenie?id=… — ogłoszenie sołectwa (link z feedu i z profilu FB sołtysa)
    invite: '/zaproszenie',
    announcement: '/ogloszenie',
    // /nowe-haslo?token=… — link z maila resetu hasła (token strona zdejmuje z adresu)
    'reset-password': '/nowe-haslo',
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

/** Zakładka profilu wskazana w adresie — `/profil?zakladka=firma` z maila
 *  o decyzji w sprawie wizytówki, `solectwo` z instrukcji dla sołtysa,
 *  `solectwa-admin` z dzwonka do redakcji. */
type ProfileTab = 'profile' | 'password' | 'preferences' | 'subscription' | 'polecaj' | 'firma' | 'solectwo' | 'solectwa-admin';
const URL_TABS: ProfileTab[] = ['firma', 'solectwo', 'solectwa-admin'];
const tabFromUrl = (): ProfileTab | undefined => {
    const tab = new URLSearchParams(window.location.search).get('zakladka') as ProfileTab | null;
    return tab && URL_TABS.includes(tab) ? tab : undefined;
};

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
    const { user, isAuthenticated, isLoading, logout, refreshUser } = useAuth();

    const [profileInitialTab, setProfileInitialTab] = useState<ProfileTab | undefined>(() => tabFromUrl());
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

    // Pomiar wejść do sekcji. To JEDYNE miejsce, które trzeba podpiąć: `activeSection`
    // jest źródłem prawdy dla całej nawigacji, więc efekt łapie i pierwsze wejście,
    // i każde kliknięcie w menu, i przycisk wstecz. Log serwera widzi wyłącznie
    // pierwsze żądanie HTML, bo to SPA bez react-routera.
    useEffect(() => {
        track('view', { section: activeSection, path: SECTION_TO_PATH[activeSection] ?? '/' });
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
        if (activeSection === 'reset-password') {
            return <PasswordResetPage onNavigate={handleNavigate} />;
        }
        if (activeSection === 'register') {
            return <RegisterPage onNavigate={handleNavigate} />;
        }
        if (activeSection === 'invite') {
            // Po przyjęciu zaproszenia (nowe konto albo istniejące) — prosto do panelu sołectwa
            const toPanel = () => {
                refreshUser();
                setProfileInitialTab('solectwo');
                setActiveSection('profile');
                setActiveTab(SECTION_TO_TAB['profile']);
                syncUrl('profile');
                window.scrollTo({ top: 0 });
            };
            return <InvitePage onDone={toPanel} onNavigate={handleNavigate} />;
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
            case 'cinema':
                return <CinemaPage />;
            case 'council':
                return <CouncilPage />;
            case 'announcement':
                return <SolectwoPostPage />;
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
                        <div>
                            <button
                                onClick={() => handleNavigate('business')}
                                className="inline-flex min-h-[44px] items-center gap-1.5 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline"
                            >
                                <ArrowLeft size={16} aria-hidden />
                                Wróć do firm
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
                    <div className="max-w-5xl space-y-6 lg:space-y-8">
                        <PageHead
                            title="Wybierz swój plan"
                            sub="Wspieraj lokalne dziennikarstwo i zyskaj dostęp do ekstra funkcji."
                        />
                        <PricingCards
                            currentTier={user?.tier || 'free'}
                            onSelect={startCheckout}
                        />

                        {/* Przebieg zakupu opisany jawnie — kupujący (i weryfikator Przelewy24)
                            musi znać kolejne kroki i warunki przed założeniem konta */}
                        <div className="grid grid-cols-1 gap-px bg-tv-seam md:grid-cols-2">
                            <section className="border-t-2 border-tv-blue bg-tv-panel p-5 sm:p-6">
                                <h3 className="font-cond mb-4 text-[20px] font-extrabold text-white">Jak kupić dostęp</h3>
                                <ol className="space-y-3 text-[15px] leading-snug text-[#d7dbe8]">
                                    <li className="flex gap-3"><span className="font-cond tabular w-4 shrink-0 font-extrabold text-tv-bluesoft">1.</span><span>Wybierz plan powyżej (Premium lub Firma lokalna) i okres rozliczeniowy — miesięczny albo roczny.</span></li>
                                    <li className="flex gap-3"><span className="font-cond tabular w-4 shrink-0 font-extrabold text-tv-bluesoft">2.</span><span>Na stronie <strong className="text-white">Podsumowanie zamówienia</strong> sprawdź cenę i zakres planu, po czym zaakceptuj Regulamin.</span></li>
                                    <li className="flex gap-3"><span className="font-cond tabular w-4 shrink-0 font-extrabold text-tv-bluesoft">3.</span><span>Załóż konto lub zaloguj się — dostęp do planu jest przypisany do konta w serwisie.</span></li>
                                    <li className="flex gap-3"><span className="font-cond tabular w-4 shrink-0 font-extrabold text-tv-bluesoft">4.</span><span>Potwierdź zamówienie z obowiązkiem zapłaty i przejdź do bramki Przelewy24 — BLIK, karta lub przelew online.</span></li>
                                    <li className="flex gap-3"><span className="font-cond tabular w-4 shrink-0 font-extrabold text-tv-bluesoft">5.</span><span>Po zaksięgowaniu płatności plan aktywuje się automatycznie, a potwierdzenie trafia na Twój e-mail.</span></li>
                                </ol>
                            </section>

                            <section className="space-y-4 border-t-2 border-tv-seam bg-tv-panel p-5 text-[15px] text-[#d7dbe8] sm:p-6">
                                <div>
                                    <h3 className="font-cond mb-2 text-[20px] font-extrabold text-white">Sprzedawca</h3>
                                    <p className="leading-relaxed">
                                        Studio Kamienia Naturalnego Lu-Mar-Go Łukasz Marchlewicz<br />
                                        Żabiny 96, 13-220 Rybno<br />
                                        NIP: <span className="tabular">571-156-78-15</span><br />
                                        <a href="tel:+48501081723" className="tabular text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline">+48 501 081 723</a>
                                        {' · '}
                                        <a href="mailto:biuro@lumargo.pl" className="text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline">biuro@lumargo.pl</a>
                                    </p>
                                </div>
                                <div>
                                    <h4 className="mb-1 font-bold text-white">Płatności i rezygnacja</h4>
                                    <p className="leading-relaxed">
                                        Płatności obsługuje PayPro S.A. (Przelewy24). Ceny są cenami brutto w złotych.
                                        Płacisz z góry za wybrany okres — subskrypcja nie odnawia się automatycznie i wygasa po jego upływie.
                                        Konsumentowi przysługuje prawo odstąpienia od umowy w terminie 14 dni (szczegóły i wzór oświadczenia w Regulaminie).
                                    </p>
                                </div>
                                <p className="flex flex-wrap gap-x-4">
                                    <a href={SECTION_TO_PATH.terms} onClick={navLink('terms')} className="inline-flex min-h-[44px] items-center font-bold text-tv-bluesoft underline underline-offset-2 hover:text-white">Regulamin</a>
                                    <a href={SECTION_TO_PATH.privacy} onClick={navLink('privacy')} className="inline-flex min-h-[44px] items-center font-bold text-tv-bluesoft underline underline-offset-2 hover:text-white">Polityka prywatności</a>
                                    <a href={SECTION_TO_PATH.cookies} onClick={navLink('cookies')} className="inline-flex min-h-[44px] items-center font-bold text-tv-bluesoft underline underline-offset-2 hover:text-white">Polityka cookies</a>
                                </p>
                            </section>
                        </div>
                    </div>
                );
            default:
                return (
                    <div className="space-y-4">
                        <PageHead title="Tej sekcji jeszcze nie ma" sub="Adres prowadzi do części serwisu, której nie uruchomiliśmy." />
                        <button
                            onClick={() => handleNavigate('dashboard')}
                            className="font-cond flex min-h-[52px] items-center bg-tv-blue px-5 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff]"
                        >
                            Wróć na pulpit
                        </button>
                    </div>
                );
        }
    };

    // Loading state
    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-tv-ink">
                <div className="text-center">
                    <p className="font-cond flex items-center justify-center text-[30px] font-black text-white">
                        Rybno<span className="ml-0.5 bg-tv-blue px-1.5 py-1 text-[24px] uppercase">Live</span>
                    </p>
                    <p className="mt-3 text-[15px] text-tv-muted">Ładowanie…</p>
                </div>
            </div>
        );
    }

    // `overflow-x-clip`, nie `-hidden`: `hidden` robi z korzenia kontener
    // przewijania, więc przyklejony TopBar przyklejał się do JEGO góry i uciekał
    // razem ze stroną. `clip` obcina tak samo, ale kontenera nie tworzy
    return (
        // Jedno płaskie tło (odświeżenie 10.2026): bez wiązek światła i poświaty
        // pod całą stroną — kolor na ekranie ma nieść stan, nie dekorację
        <div className="min-h-screen bg-tv-ink text-white overflow-x-clip">

            {/* Top Bar */}
            <TopBar
                user={user}
                isAuthenticated={isAuthenticated}
                onNavigate={handleNavigate}
                activeSection={activeSection}
                navItems={TOP_NAV.map(item => ({ ...item, href: SECTION_TO_PATH[item.id] ?? '/' }))}
            />

            {/* Sub Navigation for Miasto / Dane tabs */}
            {activeTab === 'miasto' && (
                <SubNavBar
                    className="lg:hidden"
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
            {activeSection !== 'assistant' && <footer className="relative z-10 mx-auto mb-20 max-w-7xl border-t border-tv-seam px-4 py-10 text-[14px] text-tv-muted md:px-8 lg:mb-0">
                {/* Blok danych sprzedawcy — identyfikacja wymagana przy sprzedaży online.
                    Nazwa firmy w brzmieniu z CEIDG (z imieniem i nazwiskiem — dla działalności
                    jednoosobowej jest ono częścią firmy) — wymóg weryfikacji Przelewy24 */}
                <div className="flex flex-col md:flex-row justify-between gap-8 mb-6">
                    <div className="leading-relaxed">
                        <p className="mb-1 font-semibold text-tv-paper">© 2026 RybnoLive</p>
                        <p>Studio Kamienia Naturalnego Lu-Mar-Go Łukasz Marchlewicz</p>
                        <p>Żabiny 96</p>
                        <p>13-220 Rybno</p>
                        <p>NIP: 571-156-78-15</p>
                        <p className="mt-1">
                            <a href="tel:+48501081723" className="underline-offset-4 hover:text-white hover:underline transition-colors">+48 501 081 723</a>
                        </p>
                        <p>
                            <a href="mailto:biuro@lumargo.pl" className="underline-offset-4 hover:text-white hover:underline transition-colors">biuro@lumargo.pl</a>
                        </p>
                    </div>
                    <div className="flex flex-col gap-1.5 md:text-right text-tv-paper">
                        <a href={SECTION_TO_PATH.terms} onClick={navLink('terms')} className="underline-offset-4 hover:text-white hover:underline transition-colors">Regulamin</a>
                        <a href={SECTION_TO_PATH.privacy} onClick={navLink('privacy')} className="underline-offset-4 hover:text-white hover:underline transition-colors">Polityka prywatności</a>
                        <a href={SECTION_TO_PATH.cookies} onClick={navLink('cookies')} className="underline-offset-4 hover:text-white hover:underline transition-colors">Polityka cookies</a>
                        <a href={SECTION_TO_PATH.premium} onClick={navLink('premium')} className="underline-offset-4 hover:text-white hover:underline transition-colors">Cennik</a>
                    </div>
                </div>
                <div className="border-t border-tv-seam pt-4">
                    <p>Płatności: Przelewy24 (BLIK, karta, przelew online)</p>
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
