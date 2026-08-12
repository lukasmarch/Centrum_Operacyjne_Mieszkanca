import React, { useEffect, useState } from 'react';
import { Store, Phone, Clock, Sparkles, ArrowRight, Tag } from 'lucide-react';
import {
  fetchCatalog, fetchActiveAnnouncements, trackBusinessImpression, getAssetUrl, promotableCards,
  CatalogCard, ActiveAnnouncement,
} from '../src/services/businessApi';
import { AppSection } from '../types';

/**
 * Kafel „Polecane w Rybnie" — ekspozycja wizytówek planu Firma lokalna
 * i okazji z Radaru Lokalnego Biznesu na stronie głównej.
 * Fallback (brak wizytówek premium): lejek „Twoja firma może być tutaj".
 */
const PromotedBusinessesTile: React.FC<{ onNavigate?: (section: AppSection) => void }> = ({ onNavigate }) => {
  const [premium, setPremium] = useState<CatalogCard[]>([]);
  const [okazje, setOkazje] = useState<ActiveAnnouncement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([fetchCatalog(), fetchActiveAnnouncements(6)])
      .then(([catalogRes, annRes]) => {
        if (catalogRes.status === 'fulfilled') {
          setPremium(promotableCards(catalogRes.value).slice(0, 4));
        }
        if (annRes.status === 'fulfilled') {
          setOkazje(annRes.value.filter(a => a.type === 'okazja').slice(0, 2));
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const goToBusinesses = () => onNavigate?.('business');

  if (loading) {
    return (
      <div className="flex flex-col p-5 h-full animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-4 h-4 bg-gray-700 rounded" />
          <div className="w-32 h-3 bg-gray-700 rounded" />
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-gray-900/50 rounded-xl p-3">
              <div className="w-28 h-3 bg-gray-700 rounded mb-2" />
              <div className="w-40 h-3 bg-gray-700/50 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const hasContent = premium.length > 0 || okazje.length > 0;

  return (
    <div className="flex flex-col p-5 h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Store size={14} className="text-amber-400" />
          {/* Nagłówek „Polecane" tylko wtedy, gdy naprawdę jest kogo polecić */}
          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
            {hasContent ? 'Polecane w Rybnie' : 'Firmy lokalne'}
          </p>
        </div>
        {hasContent && (
          <span className="text-[9px] text-neutral-600 uppercase tracking-wider">Materiał promocyjny</span>
        )}
      </div>

      {/* Brak wizytówek do pokazania — kafel sprzedaje pierwszeństwo zamiast udawać pełny katalog */}
      {!hasContent && (
        <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 px-2">
          <span className="text-4xl">🏪</span>
          <p className="text-sm font-bold text-neutral-200">Bądź pierwszy i przejmij swoją wizytówkę</p>
          <p className="text-xs text-neutral-500 leading-relaxed">
            To miejsce czeka na pierwszą firmę z gminy. Wizytówki trafiają na stronę główną,
            do feedu i newslettera. Przejęcie jest darmowe.
          </p>
          <button
            onClick={goToBusinesses}
            className="mt-1 px-4 py-2 bg-gradient-to-r from-amber-600 to-orange-600 text-white text-xs font-bold rounded-xl hover:from-amber-500 hover:to-orange-500 transition-all flex items-center gap-1.5"
          >
            Przejmij wizytówkę <ArrowRight size={12} />
          </button>
        </div>
      )}

      {hasContent && (
        <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-gray-700">
          {/* Okazje „tu i teraz" — Radar Lokalnego Biznesu */}
          {okazje.length > 0 && (
            <>
              <p className="text-[9px] font-bold text-amber-500/80 uppercase tracking-wider flex items-center gap-1.5">
                <Tag size={10} /> Okazje tu i teraz
              </p>
              {okazje.map(o => (
                <button
                  key={o.id}
                  onClick={() => { trackBusinessImpression(o.business_id); goToBusinesses(); }}
                  className="w-full text-left bg-amber-500/10 border border-amber-500/25 rounded-xl px-3 py-2.5 hover:bg-amber-500/15 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-amber-200">{o.title}</span>
                    {o.valid_until && (
                      <span className="text-[10px] text-amber-400 font-medium whitespace-nowrap flex items-center gap-1">
                        <Clock size={9} />
                        do {new Date(o.valid_until).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-neutral-300 mt-0.5 line-clamp-2">{o.body}</p>
                  <p className="text-[10px] text-neutral-500 mt-1">{o.nazwa} · {o.miasto}</p>
                </button>
              ))}
            </>
          )}

          {/* Wizytówki premium */}
          {premium.length > 0 && (
            <>
              <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-1.5 mt-1">
                <Sparkles size={10} /> Firmy lokalne
              </p>
              {premium.map(card => (
                <button
                  key={card.id}
                  onClick={() => { trackBusinessImpression(card.id); goToBusinesses(); }}
                  className="w-full text-left bg-gray-900/40 border border-white/5 rounded-xl px-3 py-2.5 hover:border-amber-500/30 transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    {card.profile.logo_url ? (
                      <img src={getAssetUrl(card.profile.logo_url)} alt="" className="w-8 h-8 rounded-lg object-cover flex-shrink-0" />
                    ) : (
                      <span className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center text-sm flex-shrink-0">🏪</span>
                    )}
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-white truncate">{card.nazwa}</p>
                      <p className="text-[10px] text-neutral-500 truncate">
                        {[card.branza, card.miasto].filter(Boolean).join(' · ')}
                      </p>
                    </div>
                  </div>
                  {card.profile.telefon && (
                    <p className="text-[10px] text-blue-400 mt-1.5 ml-[42px] flex items-center gap-1">
                      <Phone size={8} /> {card.profile.telefon}
                    </p>
                  )}
                </button>
              ))}
            </>
          )}

          {/* CTA na dole — lejek dla kolejnych firm */}
          <button
            onClick={goToBusinesses}
            className="w-full text-center text-[11px] text-neutral-500 hover:text-amber-400 transition-colors py-2 flex items-center justify-center gap-1"
          >
            Zobacz katalog firm <ArrowRight size={11} />
          </button>
        </div>
      )}
    </div>
  );
};

export default PromotedBusinessesTile;
