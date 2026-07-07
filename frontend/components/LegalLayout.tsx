import React from 'react';

interface LegalLayoutProps {
  title: string;
  updated: string;
  children: React.ReactNode;
}

/**
 * Wspólny layout dokumentów prawnych (Regulamin, Polityka prywatności, Cookies).
 * Typografia przez selektory arbitralne — treść stron pisana czystym HTML.
 */
export const LegalLayout: React.FC<LegalLayoutProps> = ({ title, updated, children }) => (
  <div
    className="max-w-3xl mx-auto py-6 text-neutral-300
      [&_h2]:text-white [&_h2]:text-lg [&_h2]:font-bold [&_h2]:mt-8 [&_h2]:mb-3
      [&_h3]:text-white [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-5 [&_h3]:mb-2
      [&_p]:mb-3 [&_p]:text-sm [&_p]:leading-relaxed
      [&_ul]:list-disc [&_ul]:ml-5 [&_ul]:mb-3 [&_ul]:text-sm [&_ul]:space-y-1
      [&_ol]:list-decimal [&_ol]:ml-5 [&_ol]:mb-3 [&_ol]:text-sm [&_ol]:space-y-1
      [&_li]:leading-relaxed
      [&_strong]:text-neutral-100
      [&_table]:w-full [&_table]:text-xs [&_table]:mb-4 [&_table]:border-collapse
      [&_th]:text-left [&_th]:text-neutral-400 [&_th]:font-semibold [&_th]:py-2 [&_th]:px-2 [&_th]:border-b [&_th]:border-white/10
      [&_td]:py-2 [&_td]:px-2 [&_td]:border-b [&_td]:border-white/5 [&_td]:align-top"
  >
    <h1 className="text-2xl md:text-3xl font-black text-white mb-1">{title}</h1>
    <p className="text-xs text-neutral-500 mb-6">
      Wersja z dnia {updated} · RybnoLive.pl — Centrum Operacyjne Mieszkańca
    </p>
    {children}
  </div>
);

export default LegalLayout;
