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
    <div className="min-h-screen bg-black text-neutral-100">
      {/* Page Header */}
      <div className="bg-gray-950/50 backdrop-blur-xl border-b border-gray-800/50 shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-black text-neutral-100 tracking-tight">Statystyki GUS</h1>
              <p className="text-neutral-400 mt-1 font-medium">
                Bank Danych Lokalnych GUS · Gmina Rybno · Powiat Działdowski
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Section Navigation - always visible */}
      <div className="bg-gray-950 border-b border-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <SectionNav
            activeSection={activeSection}
            onSectionChange={handleSectionChange}
            userTier={user?.tier || 'free'}
          />
        </div>
      </div>

      {/* Main Content - Conditional Rendering */}
      <div className="py-8">
        {activeSection === 'overview' ? (
          /* Overview - Free tier dashboard */
          <div className="max-w-7xl mx-auto px-4">
            <GUSOverview />
          </div>
        ) : (
          /* Section Page - Premium tier detailed view */
          <GUSSectionPage
            sectionKey={activeSection}
            onBack={handleBack}
          />
        )}
      </div>

    </div>
  );
};

export default GUSPage;
