import React, { useState } from 'react';
import {
  Building2,
  TreePine,
  Music,
  Bus,
  AlertTriangle,
  GraduationCap,
  Heart,
  Trophy,
  Newspaper,
  Waves,
  Shield,
  Megaphone,
} from 'lucide-react';

interface ArticleImageProps {
  imageUrl?: string;
  category?: string;
  source?: string;
  className?: string;
  iconSize?: 'sm' | 'md' | 'lg';
}

/**
 * Category visual config – gradient + icon + badge colors.
 * Shared design language across NewsTile, NewsFeed, and ArticleImage.
 */
export const CATEGORY_THEME: Record<
  string,
  { gradient: string; Icon: React.FC<any>; badge: string; dot: string }
> = {
  urząd: { gradient: 'from-blue-600/80 to-blue-900', Icon: Building2, badge: 'text-blue-300 bg-blue-500/20 border-blue-400/30', dot: 'bg-blue-400' },
  rekreacja: { gradient: 'from-emerald-600/80 to-teal-900', Icon: TreePine, badge: 'text-emerald-300 bg-emerald-500/20 border-emerald-400/30', dot: 'bg-emerald-400' },
  kultura: { gradient: 'from-violet-600/80 to-purple-900', Icon: Music, badge: 'text-violet-300 bg-violet-500/20 border-violet-400/30', dot: 'bg-violet-400' },
  transport: { gradient: 'from-amber-500/80 to-orange-800', Icon: Bus, badge: 'text-amber-300 bg-amber-500/20 border-amber-400/30', dot: 'bg-amber-400' },
  awaria: { gradient: 'from-red-500/80 to-rose-900', Icon: AlertTriangle, badge: 'text-red-300 bg-red-500/20 border-red-400/30', dot: 'bg-red-400' },
  edukacja: { gradient: 'from-cyan-500/80 to-sky-800', Icon: GraduationCap, badge: 'text-cyan-300 bg-cyan-500/20 border-cyan-400/30', dot: 'bg-cyan-400' },
  zdrowie: { gradient: 'from-pink-500/80 to-rose-800', Icon: Heart, badge: 'text-pink-300 bg-pink-500/20 border-pink-400/30', dot: 'bg-pink-400' },
  sport: { gradient: 'from-orange-500/80 to-amber-800', Icon: Trophy, badge: 'text-orange-300 bg-orange-500/20 border-orange-400/30', dot: 'bg-orange-400' },
  bezpieczeństwo: { gradient: 'from-yellow-500/80 to-amber-900', Icon: Shield, badge: 'text-yellow-300 bg-yellow-500/20 border-yellow-400/30', dot: 'bg-yellow-400' },
  wiadomości: { gradient: 'from-indigo-600/80 to-indigo-900', Icon: Megaphone, badge: 'text-indigo-300 bg-indigo-500/20 border-indigo-400/30', dot: 'bg-indigo-400' },
  środowisko: { gradient: 'from-lime-600/80 to-green-900', Icon: Waves, badge: 'text-lime-300 bg-lime-500/20 border-lime-400/30', dot: 'bg-lime-400' },
};

const DEFAULT_THEME = {
  gradient: 'from-slate-700/80 to-slate-900',
  Icon: Newspaper,
  badge: 'text-slate-300 bg-slate-500/20 border-slate-400/30',
  dot: 'bg-slate-400',
};

export function getCategoryTheme(category?: string) {
  if (!category) return DEFAULT_THEME;
  const key = category.toLowerCase();
  // Try exact match first, then partial match
  if (CATEGORY_THEME[key]) return CATEGORY_THEME[key];
  for (const [k, v] of Object.entries(CATEGORY_THEME)) {
    if (key.includes(k) || k.includes(key)) return v;
  }
  return DEFAULT_THEME;
}

const iconSizeMap = { sm: 20, md: 32, lg: 48 };
const pulseSizeMap = { sm: 'w-12 h-12', md: 'w-20 h-20', lg: 'w-28 h-28' };
const textSizeMap = { sm: 'text-[8px]', md: 'text-[9px]', lg: 'text-[10px]' };

/**
 * Unified article image component with attractive category-themed fallback.
 * When no image is available, renders a gradient background with animated icon.
 */
const ArticleImage: React.FC<ArticleImageProps> = ({
  imageUrl,
  category,
  source,
  className = '',
  iconSize = 'md',
}) => {
  const [imgError, setImgError] = useState(false);

  if (imageUrl && !imgError) {
    return (
      <img
        src={imageUrl}
        alt=""
        className={`w-full h-full object-cover ${className}`}
        onError={() => setImgError(true)}
        loading="lazy"
      />
    );
  }

  const theme = getCategoryTheme(category);
  const { Icon } = theme;
  const pxSize = iconSizeMap[iconSize];

  return (
    <div className={`w-full h-full relative overflow-hidden flex items-center justify-center bg-gradient-to-br ${theme.gradient} ${className}`}>
      {/* Decorative radiating circles */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className={`${pulseSizeMap[iconSize]} rounded-full bg-white/5 animate-ping`} style={{ animationDuration: '3s' }} />
      </div>
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className={`${pulseSizeMap[iconSize]} rounded-full bg-white/[0.03]`}
          style={{ transform: 'scale(1.8)' }}
        />
      </div>

      {/* Subtle grain overlay */}
      <div
        className="absolute inset-0 opacity-[0.08]"
        style={{
          backgroundImage:
            'radial-gradient(circle at 25% 25%, rgba(255,255,255,0.15) 1px, transparent 1px), radial-gradient(circle at 75% 75%, rgba(255,255,255,0.1) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
        }}
      />

      {/* Icon + source label */}
      <div className="relative flex flex-col items-center justify-center gap-2 px-3 text-center z-10">
        <Icon size={pxSize} className="text-white/30" strokeWidth={1.5} />
        {source && iconSize !== 'sm' && (
          <span className={`text-white/40 uppercase tracking-widest font-bold ${textSizeMap[iconSize]}`}>
            {source}
          </span>
        )}
      </div>
    </div>
  );
};

export default ArticleImage;
