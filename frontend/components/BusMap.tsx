import React, { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { ActiveBus, BusStop, BusTripTimetable } from '../types';
import { getCoordinatesForBus, getBearingForBus, serviceTypeLabel } from '../src/services/busLogic';

// ── Ikona przystanku ────────────────────────────────────────────────────────
const stopIconSvg = `data:image/svg+xml;base64,${btoa(
  '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">' +
  '<circle cx="10" cy="10" r="5" fill="white" stroke="#2563eb" stroke-width="3"/>' +
  '</svg>'
)}`;

const stopIcon = L.icon({ iconUrl: stopIconSvg, iconSize: [14, 14], iconAnchor: [7, 7] });

// ── Ikona autobusu ──────────────────────────────────────────────────────────
const createBusIcon = (bearing: number) =>
  L.divIcon({
    html: `
      <div style="position:relative;width:64px;height:64px;display:flex;align-items:center;justify-content:center;">
        <div style="position:absolute;width:54px;height:54px;background:rgba(37,99,235,0.25);border-radius:50%;animation:busPulse 1.5s infinite ease-out;"></div>
        <div style="position:relative;width:42px;height:42px;display:flex;align-items:center;justify-content:center;transform:rotate(${bearing}deg);">
          <div style="position:absolute;top:-12px;width:0;height:0;border-left:9px solid transparent;border-right:9px solid transparent;border-bottom:14px solid #2563eb;z-index:1;"></div>
          <div style="width:40px;height:40px;background:#2563eb;border:4px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 6px 20px rgba(0,0,0,0.3);z-index:2;transform:rotate(${-bearing}deg);">
            <svg viewBox="0 0 24 24" fill="white" width="18" height="18">
              <path d="M18 11V7a2 2 0 00-2-2H8a2 2 0 00-2 2v4m12 0a2 2 0 012 2v3a2 2 0 01-2 2h-1a2 2 0 01-2-2v-1H7v1a2 2 0 01-2 2H4a2 2 0 01-2-2v-3a2 2 0 012-2m14 0H4M8 11h2m4 0h2"/>
            </svg>
          </div>
        </div>
      </div>
      <style>@keyframes busPulse{0%{transform:scale(0.6);opacity:1}100%{transform:scale(1.7);opacity:0}}</style>
    `,
    className: '',
    iconSize: [64, 64],
    iconAnchor: [32, 32],
  });

// ── Kontroler mapy (auto-centering) ────────────────────────────────────────
function MapController({ activeBuses, stops }: { activeBuses: ActiveBus[]; stops: BusStop[] }) {
  const map = useMap();
  const lockedRef = useRef(false);

  useEffect(() => {
    if (activeBuses.length > 0) {
      const coords = getCoordinatesForBus(activeBuses[0], stops);
      if (coords) {
        map.setView([coords.lat, coords.lng], 13, { animate: true });
        lockedRef.current = true;
      }
    } else if (!lockedRef.current && stops.length > 0) {
      const bounds = L.latLngBounds(stops.map(s => [s.lat, s.lng]));
      map.fitBounds(bounds, { padding: [40, 40] });
    }
  }, [activeBuses, stops, map]);

  return null;
}

// ── Popup przystanku z godzinami ────────────────────────────────────────────
function StopPopup({
  stop,
  trips,
}: {
  stop: BusStop;
  trips: { RYBNO_DZIALDOWO: BusTripTimetable[]; DZIALDOWO_RYBNO: BusTripTimetable[] };
}) {
  const rydTimes = trips.RYBNO_DZIALDOWO
    .filter(t => t.stop_times[stop.stop_id])
    .map(t => ({ time: t.stop_times[stop.stop_id], svc: t.service_type }));

  const dzaTimes = trips.DZIALDOWO_RYBNO
    .filter(t => t.stop_times[stop.stop_id])
    .map(t => ({ time: t.stop_times[stop.stop_id], svc: t.service_type }));

  const svcColor = (s: string) =>
    s === 'GS' ? '#22c55e' : s === 'S' ? '#3b82f6' : '#f59e0b';

  return (
    <div style={{ minWidth: 160, fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ fontWeight: 800, fontSize: 11, color: '#1e293b', marginBottom: 8, letterSpacing: 0.5 }}>
        {stop.name.toUpperCase()}
      </div>
      {rydTimes.length > 0 && (
        <div style={{ marginBottom: 6 }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: '#6366f1', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
            ➔ Działdowo
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {rydTimes.map((t, i) => (
              <span key={i} style={{
                fontSize: 11, fontWeight: 700, padding: '2px 6px',
                background: '#f1f5f9', borderRadius: 6, color: '#1e293b',
                borderLeft: `3px solid ${svcColor(t.svc)}`,
              }}>
                {t.time}
              </span>
            ))}
          </div>
        </div>
      )}
      {dzaTimes.length > 0 && (
        <div>
          <div style={{ fontSize: 9, fontWeight: 700, color: '#3b82f6', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
            ➔ Rybno
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {dzaTimes.map((t, i) => (
              <span key={i} style={{
                fontSize: 11, fontWeight: 700, padding: '2px 6px',
                background: '#f1f5f9', borderRadius: 6, color: '#1e293b',
                borderLeft: `3px solid ${svcColor(t.svc)}`,
              }}>
                {t.time}
              </span>
            ))}
          </div>
        </div>
      )}
      <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid #e2e8f0', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {[['GS', '#22c55e', 'Zawsze'], ['S', '#3b82f6', 'Szkolny'], ['G', '#f59e0b', 'Wolne']].map(([k, c, l]) => (
          <span key={k} style={{ fontSize: 9, color: '#64748b', display: 'flex', alignItems: 'center', gap: 3 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: c, display: 'inline-block' }} />
            {k} – {l}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Główny komponent mapy ────────────────────────────────────────────────────
interface BusMapProps {
  activeBuses: ActiveBus[];
  stops: BusStop[];
  trips: { RYBNO_DZIALDOWO: BusTripTimetable[]; DZIALDOWO_RYBNO: BusTripTimetable[] };
}

const BusMap: React.FC<BusMapProps> = ({ activeBuses, stops, trips }) => {
  const routeCoords = useMemo(
    () => [...stops].sort((a, b) => a.sequence - b.sequence).map(s => [s.lat, s.lng] as [number, number]),
    [stops]
  );
  const center: [number, number] = [53.315, 20.06];

  return (
    <div className="w-full h-64 rounded-2xl overflow-hidden border border-black/10 relative" style={{ background: '#f8fafc' }}>
      <MapContainer
        center={center}
        zoom={11}
        scrollWheelZoom={false}
        attributionControl={false}
        className="h-full w-full"
      >
        <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />

        {/* Poświata trasy */}
        <Polyline positions={routeCoords} pathOptions={{ color: '#3b82f6', weight: 8, opacity: 0.15 }} />
        {/* Główna linia */}
        <Polyline positions={routeCoords} pathOptions={{ color: '#1d4ed8', weight: 3, opacity: 0.85 }} />

        {/* Przystanki z popupami */}
        {stops.map(stop => (
          <Marker key={stop.stop_id} position={[stop.lat, stop.lng]} icon={stopIcon}>
            <Popup className="custom-popup" maxWidth={220}>
              <StopPopup stop={stop} trips={trips} />
            </Popup>
          </Marker>
        ))}

        {/* Aktywne autobusy */}
        {activeBuses.map((bus, idx) => {
          const coords = getCoordinatesForBus(bus, stops);
          if (!coords) return null;
          const bearing = getBearingForBus(bus, stops);
          return (
            <Marker
              key={`bus-${idx}`}
              position={[coords.lat, coords.lng]}
              icon={createBusIcon(bearing)}
              zIndexOffset={2000}
            >
              <Popup>
                <div style={{ fontFamily: 'system-ui', padding: 4 }}>
                  <div style={{ fontSize: 9, fontWeight: 800, color: '#2563eb', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>
                    W TRASIE
                  </div>
                  <div style={{ fontWeight: 800, color: '#1e293b', marginBottom: 2 }}>
                    {bus.direction === 'RYBNO_DZIALDOWO' ? '➔ Działdowo' : '➔ Rybno'}
                  </div>
                  <div style={{ fontSize: 10, color: '#64748b' }}>
                    Kurs {bus.departure_time} · {serviceTypeLabel(bus.service_type)}
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        <MapController activeBuses={activeBuses} stops={stops} />
      </MapContainer>

      {/* ── Legenda (light mode) ── */}
      <div className="absolute bottom-4 left-4 z-[1000] bg-white/90 backdrop-blur-sm px-3 py-2.5 rounded-xl border border-black/10 shadow-md flex flex-col gap-2 pointer-events-none">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full border-2 border-blue-600 bg-white" />
          <span className="text-[9px] font-bold text-slate-600 uppercase tracking-wide">Przystanek</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-5 h-[3px] bg-blue-700 rounded-full" />
          <span className="text-[9px] font-bold text-slate-600 uppercase tracking-wide">Trasa</span>
        </div>
        {activeBuses.length > 0 && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-600" />
            <span className="text-[9px] font-bold text-blue-700 uppercase tracking-wide">Autobus</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default BusMap;
