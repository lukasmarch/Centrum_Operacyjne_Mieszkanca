
import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import { AppSection } from './types';

const App: React.FC = () => {
  const [activeSection, setActiveSection] = useState<AppSection>('dashboard');

  const renderContent = () => {
    switch (activeSection) {
      case 'dashboard':
        return <Dashboard />;
      case 'news':
        return (
            <div className="p-8 text-center bg-white rounded-3xl border border-dashed border-slate-200">
                <h3 className="text-xl font-bold mb-2">Agregator Wiadomości</h3>
                <p className="text-slate-500">Tutaj pojawią się wiadomości ze wszystkich 10+ źródeł lokalnych.</p>
            </div>
        );
      case 'stats':
        return (
            <div className="p-8 text-center bg-white rounded-3xl border border-dashed border-slate-200">
                <h3 className="text-xl font-bold mb-2">Dashboard GUS</h3>
                <p className="text-slate-500">Zaawansowane statystyki demograficzne i gospodarcze powiatu.</p>
            </div>
        );
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
                        <button className="w-full mt-8 py-3 rounded-xl bg-white text-blue-600 font-bold shadow-lg shadow-blue-800/20">Wybierz Premium</button>
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

  return (
    <div className="flex min-h-screen">
      <Sidebar activeSection={activeSection} onSectionChange={setActiveSection} />
      
      <main className="flex-1 md:ml-64 bg-slate-50 min-h-screen transition-all duration-300">
        {/* Top Header */}
        <div className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-100 p-4 px-8 flex items-center justify-between">
            <div className="relative w-full max-w-md hidden md:block">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">🔍</span>
                <input 
                    type="text" 
                    placeholder="Szukaj informacji, wydarzeń, BIP..." 
                    className="w-full pl-10 pr-4 py-2 bg-slate-100 rounded-full text-sm border-transparent focus:bg-white focus:ring-2 focus:ring-blue-500/20 transition-all outline-none"
                />
            </div>
            <div className="flex items-center gap-4">
                <button className="relative w-10 h-10 rounded-full flex items-center justify-center hover:bg-slate-100 transition-colors">
                    <span className="text-lg">🔔</span>
                    <span className="absolute top-2 right-2 w-2 h-2 bg-rose-500 rounded-full border-2 border-white"></span>
                </button>
                <div className="flex items-center gap-2 cursor-pointer hover:bg-slate-100 p-1 pr-3 rounded-full transition-colors">
                    <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center font-bold text-blue-600 text-xs">MK</div>
                    <span className="text-sm font-semibold hidden sm:block">Mieszkaniec</span>
                </div>
            </div>
        </div>

        {/* Dynamic Content */}
        <div className="max-w-7xl mx-auto p-4 md:p-8">
            {renderContent()}
        </div>

        {/* Footer info for better UX */}
        <footer className="max-w-7xl mx-auto px-8 py-10 mt-10 border-t border-slate-200 text-slate-400 text-sm flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-4">
                <p>© 2024 Działdowo Live</p>
                <a href="#" className="hover:text-blue-600">Polityka prywatności</a>
                <a href="#" className="hover:text-blue-600">Regulamin</a>
            </div>
            <div className="flex gap-4">
                <span className="flex items-center gap-1">🟢 Serwer: Rybno-1</span>
                <span className="flex items-center gap-1">📡 API: Active</span>
            </div>
        </footer>
      </main>
    </div>
  );
};

export default App;
