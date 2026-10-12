import React from 'react';
import { ExternalLink } from 'lucide-react';
import { ChatSource } from '../src/hooks/useChat';

interface SourceChipProps {
  source: ChatSource;
}

// Plakietka źródła w tonie szwu (rzecz neutralna). Obrys 44 px to cel dotyku,
// widoczna plakietka jest niższa — tak jak plakietka nad pasem.
const SourceChip: React.FC<SourceChipProps> = ({ source }) => {
  const label = source.title || source.source_name || 'Źródło';
  const tag = 'font-cond inline-flex max-w-[240px] items-center gap-1.5 bg-tv-seam px-2.5 py-1 text-[13px] font-bold leading-tight text-tv-paper';
  if (source.url) {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group inline-flex min-h-[44px] items-center"
      >
        <span className={`${tag} transition-colors group-hover:bg-tv-panel2 group-hover:text-white`}>
          <span className="truncate">{label}</span>
          <ExternalLink size={12} className="shrink-0 text-tv-bluesoft" aria-hidden />
        </span>
      </a>
    );
  }
  return (
    <span className="inline-flex min-h-[44px] items-center">
      <span className={tag}>
        <span className="truncate">{label}</span>
      </span>
    </span>
  );
};

export default SourceChip;
