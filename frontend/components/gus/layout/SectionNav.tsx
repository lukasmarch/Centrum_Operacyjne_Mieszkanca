/**
 * SectionNav Component
 *
 * Navigation component for GUS dashboard sections
 * Displays 10 thematic categories with icons
 *
 * Sections:
 * 1. Przegląd (Overview) - Free
 * 2. Demografia - Premium
 * 3. Rynek Pracy - Premium
 * 4. Przedsiębiorczość - Premium
 * 5. Finanse Gminy - Premium
 * 6. Mieszkalnictwo - Premium
 * 7. Edukacja - Premium
 * 8. Transport - Premium
 * 9. Bezpieczeństwo - Premium
 * 10. Zdrowie - Premium
 * 11. Turystyka - Premium
 *
 * Features:
 * - Active section highlighting
 * - Brak dostępu = kłódka zamiast ikony (+ nazwa planu dla czytnika ekranu)
 * - Lock icons for restricted sections
 * - Responsive horizontal scroll on mobile
 */

import React from 'react';
import {
  LayoutDashboard,
  Users,
  Briefcase,
  TrendingUp,
  Wallet,
  Home,
  GraduationCap,
  HeartPulse,
  Lock,
} from 'lucide-react';
import { UserTier } from '../../../types';
import { Tag } from '../../simple/tv';

interface Section {
  key: string;
  name: string;
  icon: React.ReactNode;
  tier: UserTier;
}

interface SectionNavProps {
  activeSection: string;
  onSectionChange: (sectionKey: string) => void;
  userTier?: UserTier;
  className?: string;
}

const SECTIONS: Section[] = [
  { key: 'overview', name: 'Przegląd', icon: <LayoutDashboard size={16} />, tier: 'free' },
  { key: 'demografia', name: 'Demografia', icon: <Users size={16} />, tier: 'premium' },
  { key: 'rynek_pracy', name: 'Rynek Pracy', icon: <Briefcase size={16} />, tier: 'premium' },
  { key: 'przedsiebiorczosc', name: 'Przedsiębiorczość', icon: <TrendingUp size={16} />, tier: 'premium' },
  { key: 'finanse_gminy', name: 'Finanse Gminy', icon: <Wallet size={16} />, tier: 'premium' },
  { key: 'mieszkalnictwo', name: 'Mieszkalnictwo', icon: <Home size={16} />, tier: 'premium' },
  { key: 'edukacja', name: 'Edukacja', icon: <GraduationCap size={16} />, tier: 'premium' },
  { key: 'zdrowie', name: 'Zdrowie', icon: <HeartPulse size={16} />, tier: 'premium' },
];

const SectionNav: React.FC<SectionNavProps> = ({
  activeSection,
  onSectionChange,
  userTier = 'free',
  className = '',
}) => {
  // Check if user has access to section
  const hasAccess = (section: Section): boolean => {
    if (section.tier === 'free') return true;
    if (section.tier === 'premium' && (userTier === 'premium' || userTier === 'business')) return true;
    if (section.tier === 'business' && userTier === 'business') return true;
    return false;
  };

  return (
    <div className={className}>
      {/* Header */}
      <h2 className="flex"><Tag tone="seam">Kategorie Statystyk</Tag></h2>

      {/* Kategorie jak filtry pulpitu: kwadratowe pola 44 px, aktywne = papier.
          Szew między polami zamiast odstępów i obramowań */}
      <div className="grid grid-cols-2 gap-px border-t border-tv-seam bg-tv-seam md:grid-cols-4">
        {SECTIONS.map((section) => {
          const isActive = activeSection === section.key;
          const isAccessible = hasAccess(section);

          return (
            <button
              key={section.key}
              onClick={() => {
                if (isAccessible) {
                  onSectionChange(section.key);
                } else {
                  // TODO: Show upgrade modal
                  console.log(`Section ${section.key} requires ${section.tier} tier`);
                }
              }}
              disabled={!isAccessible && !isActive}
              aria-pressed={isActive}
              className={`font-cond flex min-h-[52px] items-center gap-2 px-3 text-left text-[15px] font-bold uppercase leading-tight tracking-wide transition-colors ${
                isActive
                  ? 'bg-tv-paper text-tv-ink'
                  : isAccessible
                    ? 'bg-tv-panel text-tv-paper hover:bg-tv-panel2 hover:text-white'
                    : 'cursor-not-allowed bg-tv-panel text-tv-muted'
              }`}
            >
              {/* Na telefonie ikona tematu ustępuje miejsca nazwie; kłódka zostaje zawsze */}
              <span className={`shrink-0 ${isAccessible ? 'hidden sm:inline' : ''} ${isActive ? '' : 'text-tv-muted'}`} aria-hidden>
                {isAccessible ? section.icon : <Lock size={16} />}
              </span>
              <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{section.name}</span>

              {/* Tier badge — only when user lacks access */}
              {section.tier !== 'free' && !isAccessible && (
                <span className="sr-only">
                  {section.tier === 'business' ? '(plan Pro)' : '(plan Premium)'}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Upgrade prompt for free users */}
      {userTier === 'free' && (
        <p className="mt-px flex flex-wrap items-center gap-x-2 bg-tv-panel px-4 py-1 text-[15px] text-tv-paper">
          <Lock size={14} className="text-tv-muted" aria-hidden />
          <span><strong className="text-white">7 kategorii Premium</strong> z pełnymi danymi dostępne po upgradzie.</span>
          <button className="inline-flex min-h-[44px] items-center font-bold text-tv-bluesoft underline-offset-4 hover:text-white hover:underline">
            Zobacz plany
          </button>
        </p>
      )}
    </div>
  );
};

export default SectionNav;
