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
 * - Tier badges (Free/Premium/Business)
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
  { key: 'overview', name: 'Przegląd', icon: <LayoutDashboard size={18} />, tier: 'free' },
  { key: 'demografia', name: 'Demografia', icon: <Users size={18} />, tier: 'premium' },
  { key: 'rynek_pracy', name: 'Rynek Pracy', icon: <Briefcase size={18} />, tier: 'premium' },
  { key: 'przedsiebiorczosc', name: 'Przedsiębiorczość', icon: <TrendingUp size={18} />, tier: 'premium' },
  { key: 'finanse_gminy', name: 'Finanse Gminy', icon: <Wallet size={18} />, tier: 'premium' },
  { key: 'mieszkalnictwo', name: 'Mieszkalnictwo', icon: <Home size={18} />, tier: 'premium' },
  { key: 'edukacja', name: 'Edukacja', icon: <GraduationCap size={18} />, tier: 'premium' },
  { key: 'zdrowie', name: 'Zdrowie', icon: <HeartPulse size={18} />, tier: 'premium' },
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

  // Get tier badge color
  const getTierBadgeColor = (tier: UserTier): string => {
    switch (tier) {
      case 'free':
        return 'bg-slate-800 text-slate-400 border border-slate-700';
      case 'premium':
        return 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20';
      case 'business':
        return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
      default:
        return 'bg-slate-800 text-slate-400';
    }
  };

  return (
    <div className={`bg-slate-900 rounded-xl shadow-sm border border-slate-800 p-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-slate-100">Kategorie Statystyk</h3>
        {userTier && (
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${getTierBadgeColor(userTier as UserTier)}`}
          >
            {userTier}
          </span>
        )}
      </div>

      {/* Sections grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
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
              className={`
                relative flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all
                ${isActive
                  ? 'border-blue-500/50 bg-blue-500/10 shadow-lg shadow-blue-500/10'
                  : isAccessible
                    ? 'border-slate-800 bg-slate-800/30 hover:border-slate-600 hover:bg-slate-800'
                    : 'border-slate-800/50 bg-slate-900 opacity-40 cursor-not-allowed grayscale'
                }
              `}
            >
              {/* Lock icon for restricted sections */}
              {!isAccessible && (
                <div className="absolute top-2 right-2">
                  <Lock size={14} className="text-gray-400" />
                </div>
              )}

              {/* Icon */}
              <div
                className={`
                  p-2 rounded-lg
                  ${isActive
                    ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30'
                    : isAccessible
                      ? 'bg-slate-800 text-slate-400 group-hover:bg-slate-700 group-hover:text-slate-200'
                      : 'bg-slate-800/50 text-slate-600'
                  }
                `}
              >
                {section.icon}
              </div>

              {/* Name */}
              <span
                className={`
                  text-xs font-semibold text-center leading-tight
                  ${isActive
                    ? 'text-blue-400'
                    : isAccessible
                      ? 'text-slate-400 group-hover:text-slate-200'
                      : 'text-slate-600'
                  }
                `}
              >
                {section.name}
              </span>

              {/* Tier badge (only for non-free) */}
              {section.tier !== 'free' && (
                <span
                  className={`
                    text-[10px] font-bold px-2 py-0.5 rounded-full uppercase
                    ${getTierBadgeColor(section.tier)}
                  `}
                >
                  {section.tier}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Upgrade prompt for free users */}
      {userTier === 'free' && (
        <div className="mt-4 p-3 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-lg">
          <p className="text-sm text-indigo-300">
            <Lock size={14} className="inline mr-1" />
            <strong>10 kategorii Premium</strong> z pełnymi danymi dostępne po upgradzie.
            <button className="ml-2 text-indigo-400 hover:text-indigo-300 font-semibold underline decoration-indigo-500/30">
              Zobacz plany
            </button>
          </p>
        </div>
      )}
    </div>
  );
};

export default SectionNav;
