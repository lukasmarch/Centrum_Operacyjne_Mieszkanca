import React from 'react';
import { Truck } from 'lucide-react';

const WasteWidgetPaywall: React.FC = () => {
  return (
    <div className="glass-panel rounded-3xl border border-white/10 overflow-hidden">
      {/* Header - identyczny jak WasteWidget */}
      <div className="p-5 border-b border-white/10 flex justify-between items-center bg-emerald-500/5 backdrop-blur-md">
        <div>
          <h2 className="font-bold text-slate-100 text-lg flex items-center gap-2">
            <Truck className="text-emerald-400" size={22} />
            Harmonogram Odbioru Śmieci
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Funkcja dostępna w planie Premium
          </p>
        </div>
      </div>

      {/* Paywall - wzorowany na Enhanced GUS */}
      <div className="p-8">
        <div className="bg-gradient-to-r from-emerald-600/20 to-green-600/20 rounded-2xl p-6 text-slate-100 shadow-xl border border-emerald-500/30">
          <div className="flex items-start gap-4">
            <div className="text-4xl">🔓</div>
            <div className="flex-1">
              <h3 className="text-xl font-bold mb-2">
                Odblokuj harmonogram wywozu śmieci
              </h3>
              <p className="text-emerald-200 mb-4 text-sm">
                Zyskaj dostęp do pełnego harmonogramu odbioru odpadów dla Twojej miejscowości.
                Nie przegap już nigdy dnia wywozu!
              </p>
              <ul className="space-y-2 mb-4 text-sm">
                <li className="flex items-center gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>Harmonogram dla 31 miejscowości powiatu działdowskiego</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>8 rodzajów odpadów (zmieszane, bio, szkło, papier...)</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>Przypomnienia o nadchodzących terminach</span>
                </li>
                <li className="flex items-center gap-2">
                  <span className="text-emerald-400">✓</span>
                  <span>+ 21 dodatkowych wskaźników GUS Premium</span>
                </li>
              </ul>
              <button className="bg-emerald-500 hover:bg-emerald-600 text-white px-6 py-2 rounded-xl font-bold text-sm transition-colors shadow-lg shadow-emerald-500/20">
                Przejdź na Premium – 29 zł/mies
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WasteWidgetPaywall;
