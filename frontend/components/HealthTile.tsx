import React from 'react';
import { Heart, Clock, Phone, Pill, Stethoscope, AlertTriangle } from 'lucide-react';
import { useHealthToday } from '../src/hooks/useHealthToday';

const CLINIC_ICONS: Record<string, string> = {
  'POZ': '🏥',
  'Stomatologiczna': '🦷',
  'Ginekologiczno-Położnicza': '👶',
  'Logopedyczna': '🗣️',
  'Gabinet Zabiegowy': '💉',
  'USG': '📡',
};

const HealthTile: React.FC = () => {
  const { data, loading, error } = useHealthToday();

  // Loading skeleton
  if (loading) {
    return (
      <div className="bg-gray-950/80 border border-gray-700/50/50 rounded-2xl p-5 h-[500px] animate-pulse">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-4 h-4 bg-gray-700 rounded" />
          <div className="w-28 h-3 bg-gray-700 rounded" />
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="bg-gray-900/50 rounded-xl p-3">
              <div className="w-24 h-3 bg-gray-700 rounded mb-2" />
              <div className="w-40 h-3 bg-gray-700/50 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-gray-950/80 border border-gray-700/50/50 rounded-2xl p-5 h-[500px]">
        <div className="flex items-center gap-2 mb-4">
          <Heart size={14} className="text-rose-400" />
          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">Twoje Zdrowie</p>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-neutral-500">Brak danych o przychodniach</p>
        </div>
      </div>
    );
  }

  const hasClinics = data && data.clinics.length > 0;
  const hasPharmacies = data && data.pharmacies.length > 0;
  const isEmpty = !hasClinics && !hasPharmacies;

  return (
    <div className="bg-gray-950/80 border border-gray-700/50/50 rounded-2xl p-5 h-[500px] flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Heart size={14} className="text-rose-400" />
          <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">Twoje Zdrowie</p>
        </div>
        {data && (
          <span className="text-[10px] text-neutral-500 capitalize">{data.day_name}</span>
        )}
      </div>

      {/* Empty state (e.g. weekend) */}
      {isEmpty && (
        <div className="flex-1 flex flex-col items-center justify-center text-center gap-2">
          <Stethoscope size={32} className="text-neutral-600" />
          <p className="text-sm text-neutral-400">Brak przyjęć na dziś</p>
          <p className="text-xs text-neutral-500">Harmonogram aktualizowany co poniedziałek</p>
        </div>
      )}

      {/* Scrollable content */}
      {!isEmpty && (
        <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-gray-700">
          {/* Clinics */}
          {hasClinics && (
            <>
              <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-1.5">
                <Stethoscope size={10} />
                Kto dziś przyjmuje
              </p>
              {data!.clinics.map((clinic) => (
                <div
                  key={clinic.clinic_name}
                  className="bg-gray-900/40 rounded-xl px-3 py-2.5 border border-white/5"
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="text-xs">{CLINIC_ICONS[clinic.clinic_name] || '🏥'}</span>
                    <span className="text-xs font-semibold text-white">{clinic.clinic_name}</span>
                  </div>
                  {clinic.doctors.map((doc, i) => (
                    <div
                      key={i}
                      className={`ml-5 mt-1 ${doc.notes ? 'border-l-2 border-amber-500/50 pl-2' : ''}`}
                    >
                      <div className="flex items-start justify-between gap-2 text-xs">
                        <span className={`${doc.notes ? 'text-amber-200' : 'text-neutral-300'} leading-snug`}>
                          {doc.name || 'Lekarz'}
                          {doc.role && (
                            <span className={`${doc.notes ? 'text-amber-400/70' : 'text-neutral-500'} ml-1 text-[10px]`}>
                              ({doc.role})
                            </span>
                          )}
                        </span>
                        <span className={`${doc.notes ? 'text-amber-400' : 'text-emerald-400'} font-medium whitespace-nowrap flex items-center gap-1 text-[11px] flex-shrink-0`}>
                          <Clock size={9} />
                          {doc.hours}
                        </span>
                      </div>
                      {doc.notes && (
                        <p className="text-[10px] text-amber-400/80 mt-0.5 flex items-start gap-1">
                          <AlertTriangle size={9} className="mt-0.5 flex-shrink-0" />
                          {doc.notes}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </>
          )}

          {/* Pharmacies */}
          {hasPharmacies && (
            <>
              <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-1.5 mt-2">
                <Pill size={10} />
                Apteka dyżurna
              </p>
              {data!.pharmacies.map((pharmacy, i) => (
                <div
                  key={i}
                  className="bg-gray-900/40 rounded-xl px-3 py-2.5 border border-white/5"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-white">{pharmacy.name}</span>
                    <span className="text-emerald-400 text-[11px] font-medium flex items-center gap-1">
                      <Clock size={9} />
                      {pharmacy.hours}
                    </span>
                  </div>
                  <p className="text-[10px] text-neutral-400 mt-0.5">{pharmacy.address}</p>
                  {pharmacy.phone && (
                    <p className="text-[10px] text-blue-400 mt-0.5 flex items-center gap-1">
                      <Phone size={8} />
                      {pharmacy.phone}
                    </p>
                  )}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default HealthTile;
