/**
 * GUSPage - Main Container for GUS Statistics Dashboard
 *
 * Routing container for GUS BDL (Bank Danych Lokalnych) statistics
 * Lightweight orchestrator for Overview and Section views
 *
 * Architecture:
 * - Overview (Free tier): GUSOverview component (9 KPI variables)
 * - Sections (Premium tier): GUSSectionPage component (full category dashboards)
 * - Navigation: SectionNav component (10 categories)
 *
 * Routes:
 * - /stats → Overview (default)
 * - /stats?section=demografia → Demografia section
 * - /stats?section=rynek_pracy → Rynek Pracy section
 * - ... etc for all 10 sections
 *
 * Total refactor:
 * - OLD: 487 lines monolith with inline charts
 * - NEW: ~150 lines routing container with modular components
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import GUSOverview from '../../components/gus/GUSOverview';
import GUSSectionPage from '../../components/gus/GUSSectionPage';
import SectionNav from '../../components/gus/layout/SectionNav';

// Valid section keys (10 Premium categories)
const VALID_SECTIONS = [
  'overview',
  'demografia',
  'rynek_pracy',
  'przedsiebiorczosc',
  'finanse_gminy',
  'mieszkalnictwo',
  'edukacja',
  'transport',
  'bezpieczenstwo',
  'zdrowie',
  'turystyka',
];

const GUSPage: React.FC = () => {
  const { user } = useAuth();
  const [activeSection, setActiveSection] = useState<string>('overview');

  // Read section from URL query params on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const section = params.get('section');

    if (section && VALID_SECTIONS.includes(section)) {
      setActiveSection(section);
    } else {
      setActiveSection('overview');
    }
  }, []);

  // Update URL when section changes
  const handleSectionChange = (sectionKey: string) => {
    setActiveSection(sectionKey);

    // Update URL without page reload
    const url = new URL(window.location.href);
    if (sectionKey === 'overview') {
      url.searchParams.delete('section');
    } else {
      url.searchParams.set('section', sectionKey);
    }
    window.history.pushState({}, '', url.toString());
  };

  // Handle back navigation
  const handleBack = () => {
    handleSectionChange('overview');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Page Header */}
      <div className="bg-slate-900/50 backdrop-blur-xl border-b border-slate-800 shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-black text-slate-100 tracking-tight">Statystyki GUS</h1>
              <p className="text-slate-400 mt-1 font-medium">
                Bank Danych Lokalnych GUS · Gmina Rybno · Powiat Działdowski
              </p>
            </div>

            {/* Tier badge */}
            {user && (
              <div className="text-right">
                <p className="text-xs text-slate-400 mb-1 uppercase tracking-wider font-bold">Twój plan</p>
                <span
                  className={`inline-block px-4 py-2 rounded-full text-xs font-black uppercase tracking-wider ${user.tier === 'free'
                      ? 'bg-slate-800 text-slate-300 border border-slate-700'
                      : user.tier === 'premium'
                        ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    }`}
                >
                  {user.tier}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Section Navigation (only show if not on overview) */}
      {activeSection !== 'overview' && (
        <div className="bg-slate-900 border-b border-slate-800">
          <div className="max-w-7xl mx-auto px-4 py-4">
            <SectionNav
              activeSection={activeSection}
              onSectionChange={handleSectionChange}
              userTier={user?.tier || 'free'}
            />
          </div>
        </div>
      )}

      {/* Main Content - Conditional Rendering */}
      <div className="py-8">
        {activeSection === 'overview' ? (
          /* Overview - Free tier dashboard */
          <div className="max-w-7xl mx-auto px-4">
            <GUSOverview />

            {/* Section Navigation below overview */}
            <div className="mt-12">
              <h2 className="text-2xl font-bold text-slate-100 mb-6">Odkryj więcej kategorii</h2>
              <SectionNav
                activeSection={activeSection}
                onSectionChange={handleSectionChange}
                userTier={user?.tier || 'free'}
              />
            </div>
          </div>
        ) : (
          /* Section Page - Premium tier detailed view */
          <GUSSectionPage
            sectionKey={activeSection}
            onBack={handleBack}
          />
        )}
      </div>

      {/* Footer */}
      <div className="bg-slate-900 border-t border-slate-800 mt-12">
        <div className="max-w-7xl mx-auto px-4 py-12">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12 text-sm text-slate-400">
            <div>
              <h3 className="font-bold text-slate-200 mb-4 text-lg">O danych GUS</h3>
              <p className="leading-relaxed">
                Dane pochodzą z Banku Danych Lokalnych GUS (bdl.stat.gov.pl).
                Statystyki są aktualizowane kwartalnie i przechowywane lokalnie
                dla szybkiego dostępu.
              </p>
            </div>
            <div>
              <h3 className="font-bold text-slate-200 mb-4 text-lg">Dostępne plany</h3>
              <ul className="space-y-3">
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-slate-500"></div>
                  <span><strong>Free:</strong> 9 podstawowych wskaźników</span>
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-indigo-500"></div>
                  <span><strong>Premium (19 PLN/mies):</strong> 57 wskaźników, 10 kategorii</span>
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-amber-500"></div>
                  <span><strong>Business (99 PLN/mies):</strong> 88 wskaźników, AI insights</span>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="font-bold text-slate-200 mb-4 text-lg">Źródła danych</h3>
              <ul className="space-y-2">
                <li>• Gmina Rybno (kod TERYT: 042815403062)</li>
                <li>• Powiat Działdowski (kod TERYT: 042815403000)</li>
                <li>• Województwo warmińsko-mazurskie</li>
                <li>• Polska (średnie krajowe)</li>
              </ul>
            </div>
          </div>

          <div className="mt-12 pt-8 border-t border-slate-800 text-center text-xs text-slate-600">
            <p>
              Dane GUS © Główny Urząd Statystyczny · Ostatnia aktualizacja:{' '}
              {new Date().toLocaleDateString('pl-PL', {
                year: 'numeric',
                month: 'long',
              })}
            </p>
            <p className="mt-2">
              Centrum Operacyjne Mieszkańca · Powiat Działdowski · 2026
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GUSPage;
