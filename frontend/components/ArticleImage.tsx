import React, { useState } from 'react';

interface ArticleImageProps {
  imageUrl?: string;
  category?: string;
  source?: string;
  className?: string;
  iconSize?: 'sm' | 'md' | 'lg';
}

/**
 * Unified article image component with monochromatic category-based fallback.
 * Falls back to dark placeholder with category text + source when image is missing or broken.
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
      />
    );
  }

  const textSize = iconSize === 'sm' ? 'text-xs' : iconSize === 'lg' ? 'text-xl' : 'text-base';
  const displayCategory = (category || 'INFO').toUpperCase();

  return (
    <div className={`w-full h-full bg-slate-900 relative overflow-hidden flex items-center justify-center ${className}`}>
      {/* Subtle grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />
      <div className="relative flex flex-col items-center justify-center gap-1.5 px-3 text-center">
        <span className={`text-slate-700 font-black uppercase tracking-[.25em] ${textSize}`}>
          {displayCategory}
        </span>
        {source && (
          <span className="text-slate-600 text-[9px] uppercase tracking-wider">{source}</span>
        )}
      </div>
    </div>
  );
};

export default ArticleImage;
