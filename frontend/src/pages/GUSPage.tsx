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
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-black text-neutral-100 tracking-tight">Statystyki GUS</h1>
        <p className="text-neutral-400 mt-1 font-medium">
          Bank Danych Lokalnych GUS · Gmina Rybno · Powiat Działdowski
        </p>
      </div>

      {/* Section Navigation - always visible */}
      <div className="border-b border-white/5 pb-4">
        <SectionNav
          activeSection={activeSection}
          onSectionChange={handleSectionChange}
          userTier={user?.tier || 'free'}
        />
      </div>

      {/* Main Content - Conditional Rendering */}
      <div>
        {activeSection === 'overview' ? (
          <GUSOverview />
        ) : (
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
