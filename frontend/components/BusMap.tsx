
import React, { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { ActiveBus } from '../types';
import { STOPS } from '../constants';
import { getCoordinatesForBus } from '../src/services/busLogic';

// Custom stop icon: White circle with high-contrast blue border
const stopIconSvg = `data:image/svg+xml;base64,${btoa(`
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="12" r="5" fill="white" stroke="#2563eb" stroke-width="3"/>
</svg>
`)}`;

const stopIcon = L.icon({
    iconUrl: stopIconSvg,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
});

function getBearing(lat1: number, lng1: number, lat2: number, lng2: number) {
    const y = Math.sin((lng2 - lng1) * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180);
    const x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
        Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos((lng2 - lng1) * Math.PI / 180);
    const brng = Math.atan2(y, x) * 180 / Math.PI;
    return (brng + 360) % 360;
}

const createBusIcon = (bearing: number) => {
    const iconHtml = `
    <div class="bus-marker-container">
      <div class="bus-pulse"></div>
      <div class="bus-icon-wrapper" style="transform: rotate(${bearing}deg);">
        <div class="bus-direction-arrow"></div>
        <div class="bus-circle">
          <svg viewBox="0 0 24 24" fill="white" width="18" height="18">
            <path d="M18 11V7a2 2 0 00-2-2H8a2 2 0 00-2 2v4m12 0a2 2 0 012 2v3a2 2 0 01-2 2h-1a2 2 0 01-2-2v-1H7v1a2 2 0 01-2 2H4a2 2 0 01-2-2v-3a2 2 0 012-2m14 0H4M8 11h2m4 0h2"/>
          </svg>
        </div>
      </div>
    </div>
    <style>
      .bus-marker-container {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 64px;
        height: 64px;
        position: relative;
      }
      .bus-pulse {
        position: absolute;
        width: 54px;
        height: 54px;
        background: rgba(37, 99, 235, 0.25);
        border-radius: 50%;
        animation: busPulse 1.5s infinite ease-out;
      }
      .bus-icon-wrapper {
        position: relative;
        width: 42px;
        height: 42px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
      }
      .bus-circle {
        width: 40px;
        height: 40px;
        background: #2563eb;
        border: 4px solid white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        z-index: 2;
        transform: rotate(${-bearing}deg);
      }
      .bus-direction-arrow {
        position: absolute;
        top: -12px;
        width: 0;
        height: 0;
        border-left: 9px solid transparent;
        border-right: 9px solid transparent;
        border-bottom: 14px solid #2563eb;
        z-index: 1;
      }
      @keyframes busPulse {
        0% { transform: scale(0.6); opacity: 1; }
        100% { transform: scale(1.7); opacity: 0; }
      }
    </style>
  `;

    return L.divIcon({
        html: iconHtml,
        className: '',
        iconSize: [64, 64],
        iconAnchor: [32, 32],
    });
};

function MapController({ activeBuses }: { activeBuses: ActiveBus[] }) {
    const map = useMap();
    const hasCenteredOnBus = useRef(false);

    useEffect(() => {
        if (activeBuses.length > 0) {
            const bus = activeBuses[0];
            const coords = getCoordinatesForBus(bus);

            if (coords) {
                const newPos: [number, number] = [coords.lat, coords.lng];
                // Center on the bus
                map.setView(newPos, 14, { animate: true });
                hasCenteredOnBus.current = true;
            }
        } else if (!hasCenteredOnBus.current) {
            // Only fit bounds if we haven't locked onto a bus yet
            const bounds = L.latLngBounds(STOPS.map(s => [s.lat, s.lng]));
            map.fitBounds(bounds, { padding: [50, 50] });
        }
    }, [activeBuses, map]);
    return null;
}

interface BusMapProps {
    activeBuses: ActiveBus[];
}

const BusMap: React.FC<BusMapProps> = ({ activeBuses }) => {
    const routeCoords: [number, number][] = useMemo(() => STOPS.map(s => [s.lat, s.lng]), []);
    const center: [number, number] = [53.315, 20.06];

    return (
        <div className="w-full h-64 glass-panel rounded-2xl overflow-hidden shadow-inner border border-white/10 relative">
            <MapContainer
                center={center}
                zoom={12}
                scrollWheelZoom={false}
                attributionControl={false}
                className="h-full w-full"
            >
                <TileLayer
                    url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                />

                {/* Glow trasy */}
                <Polyline
                    positions={routeCoords}
                    pathOptions={{ color: '#3b82f6', weight: 8, opacity: 0.3, lineJoin: 'round' }}
                />

                {/* Główna linia trasy - wyraźna */}
                <Polyline
                    positions={routeCoords}
                    pathOptions={{ color: '#1d4ed8', weight: 4, opacity: 0.9, lineJoin: 'round' }}
                />

                {STOPS.map(stop => (
                    <Marker
                        key={stop.id}
                        position={[stop.lat, stop.lng]}
                        icon={stopIcon}
                    >
                        <Popup className="custom-popup">
                            <div className="text-[12px] font-black text-slate-800 px-1 py-0.5">
                                {stop.name}
                            </div>
                        </Popup>
                    </Marker>
                ))}

                {activeBuses.map((bus, idx) => {
                    const coords = getCoordinatesForBus(bus);
                    if (!coords) return null;

                    const s1 = STOPS.find(s => s.id === bus.currentStopId);
                    const s2 = STOPS.find(s => s.id === bus.nextStopId);
                    const bearing = s1 && s2 ? getBearing(s1.lat, s1.lng, s2.lat, s2.lng) : 0;

                    return (
                        <Marker
                            key={`live-bus-${idx}`}
                            position={[coords.lat, coords.lng]}
                            icon={createBusIcon(bearing)}
                            zIndexOffset={2000}
                        >
                            <Popup className="bus-popup">
                                <div className="text-xs font-bold p-1">
                                    <div className="text-blue-600 uppercase text-[10px] mb-1 font-black tracking-widest">W TRASIE</div>
                                    <div className="text-slate-900 border-t border-slate-100 pt-1.5 mt-1 font-black">
                                        {bus.direction === 'RYBNO_DZIALDOWO' ? '➔ Działdowo' : '➔ Rybno'}
                                    </div>
                                </div>
                            </Popup>
                        </Marker>
                    );
                })}

                <MapController activeBuses={activeBuses} />
            </MapContainer>

            {/* Overlay legendy */}
            <div className="absolute bottom-6 left-6 z-[1000] bg-white/95 backdrop-blur-sm px-5 py-4 rounded-[2rem] shadow-2xl border border-white flex flex-col gap-3 pointer-events-none">
                <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded-full border-[2.5px] border-blue-600 bg-white shadow-sm"></div>
                    <span className="text-[10px] font-black text-slate-700 uppercase tracking-tight">Przystanek</span>
                </div>
                <div className="flex items-center gap-3">
                    <div className="w-7 h-[4px] bg-blue-700 rounded-full"></div>
                    <span className="text-[10px] font-black text-slate-700 uppercase tracking-tight">Trasa</span>
                </div>
            </div>
        </div>
    );
};

export default BusMap;
