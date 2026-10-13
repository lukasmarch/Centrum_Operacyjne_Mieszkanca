import React, { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import { MAP_ATTRIBUTION, MAP_TILE_URL } from '../src/utils/mapTiles';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { ActiveBus, BusStop, BusTripTimetable } from '../types';
import { getCoordinatesForBus, getBearingForBus, serviceTypeLabel } from '../src/services/busLogic';

// Odświeżenie „Pasek informacyjny” (10.2026): kafelki mapy zostają, wokół nich
// nic nie jest zaokrąglone ani nie ma cienia. Kółka markerów zostają — to natywny
// język mapy, nie karta. Chaber = kolor tematu (tv-blue).
const TV_BLUE = '#1f4fff';
const TV_FONT = 'Archivo, system-ui, sans-serif';

// ── Ikona przystanku ────────────────────────────────────────────────────────
const stopIconSvg = `data:image/svg+xml;base64,${btoa(
  '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">' +
  '<circle cx="10" cy="10" r="5" fill="white" stroke="#1f4fff" stroke-width="3"/>' +
  '</svg>'
)}`;

const stopIcon = L.icon({ iconUrl: stopIconSvg, iconSize: [14, 14], iconAnchor: [7, 7] });

// ── Ikona autobusu ──────────────────────────────────────────────────────────
// Bez pulsującej poświaty i cienia — kurs jest liczony z rozkładu, nie z GPS,
// więc „bijące serce” sugerowało sygnał na żywo, którego nie mamy (audyt F-039)
const createBusIcon = (bearing: number) =>
  L.divIcon({
    html: `
      <div style="position:relative;width:64px;height:64px;display:flex;align-items:center;justify-content:center;">
        <div style="position:relative;width:42px;height:42px;display:flex;align-items:center;justify-content:center;transform:rotate(${bearing}deg);">
          <div style="position:absolute;top:-12px;width:0;height:0;border-left:9px solid transparent;border-right:9px solid transparent;border-bottom:14px solid ${TV_BLUE};z-index:1;"></div>
          <div style="width:40px;height:40px;background:${TV_BLUE};border:4px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;z-index:2;transform:rotate(${-bearing}deg);">
            <svg viewBox="0 0 24 24" fill="white" width="18" height="18">
              <path d="M18 11V7a2 2 0 00-2-2H8a2 2 0 00-2 2v4m12 0a2 2 0 012 2v3a2 2 0 01-2 2h-1a2 2 0 01-2-2v-1H7v1a2 2 0 01-2 2H4a2 2 0 01-2-2v-3a2 2 0 012-2m14 0H4M8 11h2m4 0h2"/>
            </svg>
          </div>
        </div>
      </div>
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

  // Typ kursu literą przy godzinie zamiast kolorowej krawędzi: „06:40 S” = tylko
  // w dni szkolne. Kurs codzienny (GS) zostaje bez dopisku — to stan domyślny
  const times = (list: { time: string; svc: string }[]) => (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 10px' }}>
      {list.map((t, i) => (
        <span key={i} style={{ fontSize: 15, fontWeight: 700, color: '#ffffff', fontVariantNumeric: 'tabular-nums' }}>
          {t.time}
          {t.svc !== 'GS' && <span style={{ fontSize: 13, fontWeight: 600, color: '#b4bbd0', marginLeft: 3 }}>{t.svc}</span>}
        </span>
      ))}
    </div>
  );
  const dirLabel: React.CSSProperties = {
    fontSize: 13, fontWeight: 800, color: '#b4bbd0', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 2,
  };

  return (
    <div style={{ minWidth: 170, fontFamily: TV_FONT }}>
      <div style={{ fontWeight: 800, fontSize: 15, color: '#ffffff', marginBottom: 8 }}>
        {stop.name}
      </div>
      {rydTimes.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={dirLabel}>Do Działdowa</div>
          {times(rydTimes)}
        </div>
      )}
      {dzaTimes.length > 0 && (
        <div>
          <div style={dirLabel}>Do Rybna</div>
          {times(dzaTimes)}
        </div>
      )}
      <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid #222b45', fontSize: 13, color: '#b4bbd0' }}>
        S – Szkolny · G – Wolne
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
    <div className="tv-map relative h-64 w-full overflow-hidden bg-tv-panel lg:h-80">
      {/* Dymki Leaflet mają z arkusza biblioteki zaokrąglenie i cień — tu płaski panel */}
      <style>{`
        .tv-map .leaflet-popup-content-wrapper{border-radius:0;box-shadow:none;background:#121829;border:1px solid #222b45;border-top:2px solid ${TV_BLUE};color:#f5f6fa}
        .tv-map .leaflet-popup-tip{box-shadow:none;background:#121829}
        .tv-map .leaflet-popup-close-button{color:#b4bbd0}
        .tv-map .leaflet-bar{border-radius:0;box-shadow:none;border:1px solid #222b45}
        .tv-map .leaflet-bar a{border-radius:0}
      `}</style>
      <MapContainer
        center={center}
        zoom={11}
        scrollWheelZoom={false}
        className="h-full w-full"
      >
        <TileLayer url={MAP_TILE_URL} attribution={MAP_ATTRIBUTION} maxZoom={19} />

        {/* Trasa — jedna linia, bez poświaty */}
        <Polyline positions={routeCoords} pathOptions={{ color: TV_BLUE, weight: 4, opacity: 0.9 }} />

        {/* Przystanki z popupami */}
        {stops.map(stop => (
          <Marker key={stop.stop_id} position={[stop.lat, stop.lng]} icon={stopIcon}>
            <Popup className="custom-popup" maxWidth={240}>
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
                <div style={{ fontFamily: TV_FONT, padding: 2 }}>
                  <div style={{ fontSize: 13, fontWeight: 800, color: '#8fa8ff', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
                    W trasie · wg rozkładu
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 800, color: '#ffffff', marginBottom: 2 }}>
                    {bus.direction === 'RYBNO_DZIALDOWO' ? 'Do Działdowa' : 'Do Rybna'}
                  </div>
                  <div style={{ fontSize: 13, color: '#b4bbd0', fontVariantNumeric: 'tabular-nums' }}>
                    Kurs {bus.departure_time} · {serviceTypeLabel(bus.service_type)}
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        <MapController activeBuses={activeBuses} stops={stops} />
      </MapContainer>

      {/* Legenda — płaski panel w rogu, bez rozmycia i cienia */}
      <div className="pointer-events-none absolute bottom-0 left-0 z-[1000] flex flex-col gap-1.5 bg-tv-ink px-3 py-2">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full border-2 border-tv-blue bg-white" />
          <span className="text-[13px] font-semibold text-tv-paper">Przystanek</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-[3px] w-5 bg-tv-blue" />
          <span className="text-[13px] font-semibold text-tv-paper">Trasa</span>
        </div>
        {activeBuses.length > 0 && (
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-tv-blue" />
            <span className="text-[13px] font-semibold text-tv-paper">Autobus</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default BusMap;
