import React from 'react';
import { ChatSource } from '../src/hooks/useChat';

interface SourceChipProps {
  source: ChatSource;
}

const SourceChip: React.FC<SourceChipProps> = ({ source }) => (
  <a
    href={source.url}
    target="_blank"
    rel="noopener noreferrer"
    className="inline-flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-blue-400 bg-slate-800/60 border border-white/5 hover:border-blue-500/30 px-2.5 py-1 rounded-full transition-all"
  >
    <span className="w-1.5 h-1.5 rounded-full bg-blue-500/70 shrink-0" />
    {source.title || source.source_name || 'Źródło'}
  </a>
);

export default SourceChip;
