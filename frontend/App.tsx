import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import NewsFeed from './components/NewsFeed';
import EventsFeed from './components/EventsFeed';
import { AppSection } from './types';
import { DataCacheProvider } from './src/context/DataCacheContext';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import LoginPage from './src/pages/LoginPage';
import RegisterPage from './src/pages/RegisterPage';
import ProfilePage from './src/pages/ProfilePage';
import GUSPage from './src/pages/GUSPage';
import WeatherPage from './src/pages/WeatherPage';
import BusinessPage from './src/pages/BusinessPage';
import ReportsPage from './src/pages/ReportsPage';

const AppContent: React.FC = () => {
    const [activeSection, setActiveSection] = useState<AppSection>('dashboard');
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const { user, isAuthenticated, isLoading, logout } = useAuth();

    const handleNavigate = (section: AppSection | 'logout') => {
        if (section === 'logout') {
            logout();
            setActiveSection('dashboard');
        } else {
            setActiveSection(section);
        }
        // Close sidebar on mobile after navigation
        setIsSidebarOpen(false);
    };

    const renderContent = () => {
        // Auth pages (don't require login)
        if (activeSection === 'login') {
            return <LoginPage onNavigate={(page) => setActiveSection(page === 'register' ? 'register' : 'dashboard')} />;
        }
        if (activeSection === 'register') {
            return <RegisterPage onNavigate={(page) => setActiveSection(page === 'login' ? 'login' : 'dashboard')} />;
        }

        // Profile page (requires login)
        if (activeSection === 'profile') {
            if (!isAuthenticated) {
                setActiveSection('login');
                return null;
            }
            return <ProfilePage onNavigate={setActiveSection} />;
        }

        // Regular sections
        switch (activeSection) {
            case 'dashboard':
                return <Dashboard onNavigate={setActiveSection} />;
            case 'news':
                return <NewsFeed />;
            case 'events':
                return <EventsFeed />;
            case 'weather':
                return <WeatherPage />;
            case 'stats':
                return <GUSPage />;
            case 'business':
                return <BusinessPage />;
            case 'reports':
                return <ReportsPage onNavigate={setActiveSection} />;
            case 'premium':
                return (
                    <div className="max-w-4xl mx-auto py-12">
                        <div className="text-center mb-12">
                            <h2 className="text-4xl font-black mb-4">Wybierz swój plan</h2>
                            <p className="text-slate-500 text-lg">Wspieraj lokalne dziennikarstwo i zyskaj dostęp do ekstra funkcji.</p>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                            {/* Free */}
                            <div className="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm flex flex-col">
                                <h4 className="text-xl font-bold mb-2">Dla Każdego</h4>
                                <p className="text-4xl font-black mb-6">0 zł <span className="text-sm text-slate-400 font-normal">/mc</span></p>
                                <ul className="space-y-4 text-sm text-slate-600 flex-1">
                                    <li className="flex items-center gap-2">✅ Wiadomości basic</li>
                                    <li className="flex items-center gap-2">✅ Pogoda standard</li>
                                    <li className="flex items-center gap-2">✅ Newsletter tygodniowy</li>
                                </ul>
                                <button className="w-full mt-8 py-3 rounded-xl border-2 border-slate-100 font-bold text-slate-400" disabled>Aktualny plan</button>
                            </div>
                            {/* Premium */}
                            <div className="bg-blue-600 p-8 rounded-3xl shadow-xl shadow-blue-200 text-white flex flex-col transform scale-105">
                                <div className="flex justify-between items-start mb-2">
                                    <h4 className="text-xl font-bold">Premium</h4>
                                    <span className="bg-white/20 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-widest">Najczęściej wybierany</span>
                                </div>
                                <p className="text-4xl font-black mb-6">19 zł <span className="text-sm text-blue-200 font-normal">/mc</span></p>
                                <ul className="space-y-4 text-sm text-blue-50 flex-1">
                                    <li className="flex items-center gap-2">✅ AI Daily Summaries</li>
                                    <li className="flex items-center gap-2">✅ Alerty SMS / Push</li>
                                    <li className="flex items-center gap-2">✅ Brak reklam</li>
                                    <li className="flex items-center gap-2">✅ Newsletter Codzienny</li>
                                </ul>
                                <button
                                    onClick={() => !isAuthenticated && setActiveSection('register')}
                                    className="w-full mt-8 py-3 rounded-xl bg-white text-blue-600 font-bold shadow-lg shadow-blue-800/20 hover:bg-blue-50 transition-colors"
                                >
                                    {isAuthenticated ? 'Wybierz Premium' : 'Zarejestruj się'}
                                </button>
                            </div>
                            {/* Business */}
                            <div className="bg-slate-900 p-8 rounded-3xl shadow-sm text-white flex flex-col">
                                <h4 className="text-xl font-bold mb-2">Biznes</h4>
                                <p className="text-4xl font-black mb-6">99 zł <span className="text-sm text-slate-500 font-normal">/mc</span></p>
                                <ul className="space-y-4 text-sm text-slate-400 flex-1">
                                    <li className="flex items-center gap-2">✅ Dostęp do API</li>
                                    <li className="flex items-center gap-2">✅ Raporty Customowe</li>
                                    <li className="flex items-center gap-2">✅ Promocja Wydarzeń</li>
                                    <li className="flex items-center gap-2">✅ Dane historyczne GUS</li>
                                </ul>
                                <button className="w-full mt-8 py-3 rounded-xl border border-slate-700 font-bold hover:bg-slate-800 transition-colors">Skontaktuj się</button>
                            </div>
                        </div>
                    </div>
                );
            default:
                return (
                    <div className="p-20 text-center flex flex-col items-center justify-center">
                        <span className="text-6xl mb-4">🚧</span>
                        <h3 className="text-2xl font-bold">Sekcja w budowie</h3>
                        <p className="text-slate-500 max-w-sm">Ten moduł jest aktualnie opracowywany przez nasz zespół AI i developerów.</p>
                        <button onClick={() => setActiveSection('dashboard')} className="mt-6 text-blue-600 font-bold">Wróć do kokpitu</button>
                    </div>
                );
        }
    };

    // Loading state
    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <div className="text-center">
                    <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center font-bold text-3xl text-white mx-auto mb-4 animate-pulse">
                        R
                    </div>
                    <p className="text-slate-500">Ładowanie...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-blue-500/30">
            {/* Mobile overlay */}
            {isSidebarOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 md:hidden"
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            <Sidebar
                activeSection={activeSection}
                onSectionChange={handleNavigate}
                user={user}
                isOpen={isSidebarOpen}
                onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
            />

            <main className="flex-1 md:ml-64 bg-slate-950 min-h-screen transition-all duration-300 relative">
                {/* Background Gradients */}
                <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-900/20 via-slate-950 to-slate-950 pointer-events-none"></div>

                {/* Top Header */}
                <div className="relative z-40 bg-transparent p-4 px-8 flex items-center justify-between">
                    {/* Mobile hamburger button */}
                    <button
                        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                        className="md:hidden w-10 h-10 flex items-center justify-center rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
                        aria-label="Toggle menu"
                    >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            {isSidebarOpen ? (
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            ) : (
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                            )}
                        </svg>
                    </button>

                    <div className="relative w-full max-w-md hidden md:block group">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-blue-400 transition-colors">🔍</span>
                        <input
                            type="text"
                            placeholder="Szukaj informacji, wydarzeń, BIP..."
                            className="w-full pl-10 pr-4 py-2 bg-slate-800/50 rounded-full text-sm text-slate-200 border border-white/5 focus:bg-slate-800 focus:border-blue-500/50 focus:ring-2 focus:ring-blue-500/20 transition-all outline-none placeholder:text-slate-600"
                        />
                    </div>
                    <div className="flex items-center gap-4">
                        {isAuthenticated && user ? (
                            <button
                                onClick={() => setActiveSection('profile')}
                                className="group transition-transform hover:scale-105 active:scale-95"
                            >
                                <div className={`px-5 py-2 rounded-full font-bold text-white text-sm shadow-lg tracking-wide bg-gradient-to-r ${user.tier === 'business' ? 'from-blue-600 via-indigo-600 to-purple-600 shadow-indigo-500/20' :
                                    user.tier === 'premium' ? 'from-indigo-500 via-purple-500 to-pink-500 shadow-purple-500/20' :
                                        'from-slate-600 to-slate-500'
                                    }`}>
                                    {user.tier === 'business' ? 'Business' : user.tier === 'premium' ? 'Premium' : 'Free'}
                                </div>
                            </button>
                        ) : (
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setActiveSection('login')}
                                    className="flex items-center gap-2 cursor-pointer text-slate-400 hover:text-white px-4 py-2 rounded-full transition-colors font-semibold text-sm"
                                >
                                    Zaloguj
                                </button>
                                <button
                                    onClick={() => setActiveSection('register')}
                                    className="flex items-center gap-2 cursor-pointer bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 rounded-full transition-all shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40 hover:-translate-y-0.5"
                                >
                                    <span className="text-sm font-bold">Zarejestruj</span>
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* User location banner */}
                {isAuthenticated && user && (
                    <div className="relative z-30 py-2">
                        <div className="max-w-7xl mx-auto px-4">
                            <div className="w-fit mx-auto bg-slate-950/80 backdrop-blur-md border border-white/10 rounded-full py-1.5 px-6 flex items-center gap-6 shadow-xl shadow-black/20">
                                <p className="text-xs font-medium text-slate-400 flex items-center gap-3">
                                    <span className="relative flex h-2 w-2">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                                    </span>
                                    <span className="tracking-wide">Lokalizacja:</span>
                                    <strong className="text-indigo-300 font-semibold tracking-wide text-sm">{user.location}</strong>
                                </p>
                                <div className="h-4 w-px bg-white/10"></div>
                                <button
                                    onClick={() => setActiveSection('profile')}
                                    className="text-[10px] font-bold uppercase tracking-wider text-slate-500 hover:text-white transition-colors hover:underline decoration-indigo-500 decoration-2 underline-offset-4"
                                >
                                    Zmień
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Dynamic Content */}
                <div className="max-w-7xl mx-auto p-4 md:p-8 relative z-10">
                    {renderContent()}
                </div>

                {/* Footer info for better UX */}
                <footer className="max-w-7xl mx-auto px-8 py-10 mt-10 border-t border-white/5 text-slate-500 text-xs flex flex-col md:flex-row justify-between items-center gap-4 relative z-10">
                    <div className="flex items-center gap-6">
                        <p className="font-medium">© 2024 Rybno Live</p>
                        <div className="flex gap-4">
                            <a href="#" className="hover:text-blue-400 transition-colors">Prywatność</a>
                            <a href="#" className="hover:text-blue-400 transition-colors">Regulamin</a>
                        </div>
                    </div>
                    <div className="flex gap-4 font-mono opacity-50">
                        <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Rybno-1</span>
                        <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> API: v2.4</span>
                    </div>
                </footer>
            </main>
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
