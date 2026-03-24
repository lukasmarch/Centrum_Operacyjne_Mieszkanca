import React from 'react';
import { ExternalLink } from 'lucide-react';
import { ChatSource } from '../src/hooks/useChat';

interface SourceChipProps {
  source: ChatSource;
}

const SourceChip: React.FC<SourceChipProps> = ({ source }) => {
  const label = source.title || source.source_name || 'Źródło';
  if (source.url) {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-[11px] text-blue-400 hover:text-blue-300 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 hover:border-blue-400/50 px-2.5 py-1 rounded-full transition-all cursor-pointer max-w-[220px]"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
        <span className="truncate">{label}</span>
        <ExternalLink size={9} className="shrink-0 opacity-70" />
      </a>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-neutral-500 bg-gray-900/60 border border-white/5 px-2.5 py-1 rounded-full max-w-[220px]">
      <span className="w-1.5 h-1.5 rounded-full bg-neutral-600 shrink-0" />
      <span className="truncate">{label}</span>
    </span>
  );
};

export default SourceChip;
