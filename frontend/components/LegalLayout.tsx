import React from 'react';
import { PageHead } from './simple/tv';

interface LegalLayoutProps {
  title: string;
  updated: string;
  children: React.ReactNode;
}

/**
 * Wspólny layout dokumentów prawnych (Regulamin, Polityka prywatności, Cookies).
 * Typografia przez selektory arbitralne — treść stron pisana czystym HTML.
 *
 * Tryb czytania (10.2026): miara ~68 znaków, akapit 16 px / 1,6 normalną
 * szerokością kroju, nagłówki wąskim. Tabela na telefonie przewija się sama
 * (`display:block` + `overflow-x-auto`), żeby strona nie jeździła w poziomie.
 */
export const LegalLayout: React.FC<LegalLayoutProps> = ({ title, updated, children }) => (
  <div className="mx-auto max-w-[68ch] pb-6 pt-2">
    <PageHead
      title={title}
      sub={<>Wersja z dnia <span className="tabular">{updated}</span> · RybnoLive.pl — Centrum Operacyjne Mieszkańca</>}
    />
    <div
      className="mt-6 text-[16px] leading-[1.6] text-[#d7dbe8]
        [&_h2]:[font-stretch:78%] [&_h2]:tracking-[-0.01em] [&_h2]:text-[22px] [&_h2]:font-extrabold [&_h2]:leading-tight [&_h2]:text-white [&_h2]:mt-10 [&_h2]:mb-3
        [&_h3]:[font-stretch:78%] [&_h3]:text-[18px] [&_h3]:font-bold [&_h3]:leading-tight [&_h3]:text-white [&_h3]:mt-6 [&_h3]:mb-2
        [&_p]:mb-4
        [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-4 [&_ul]:space-y-1.5
        [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-4 [&_ol]:space-y-1.5
        [&_li]:marker:text-tv-muted
        [&_strong]:font-semibold [&_strong]:text-white
        [&_blockquote]:my-5 [&_blockquote]:border [&_blockquote]:border-tv-seam [&_blockquote]:bg-tv-panel [&_blockquote]:px-4 [&_blockquote]:pt-4 [&_blockquote]:pb-1
        [&_table]:mb-5 [&_table]:block [&_table]:w-full [&_table]:overflow-x-auto [&_table]:border-collapse [&_table]:text-[14px] [&_table]:leading-snug
        [&_th]:[font-stretch:78%] [&_th]:whitespace-nowrap [&_th]:border-b [&_th]:border-tv-seam [&_th]:px-2 [&_th]:py-2 [&_th]:text-left [&_th]:text-[13px] [&_th]:font-bold [&_th]:uppercase [&_th]:tracking-wide [&_th]:text-tv-muted
        [&_td]:border-b [&_td]:border-tv-seam [&_td]:px-2 [&_td]:py-2 [&_td]:align-top"
    >
      {children}
    </div>
  </div>
);

export default LegalLayout;
