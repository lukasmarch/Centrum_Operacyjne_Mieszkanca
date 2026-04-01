import { ActiveBus, BusStop } from '../../types';

/**
 * Oblicza współrzędne GPS autobusu przez interpolację liniową między przystankami.
 */
export function getCoordinatesForBus(
  bus: ActiveBus,
  stops: BusStop[]
): { lat: number; lng: number } | null {
  const stop1 = stops.find(s => s.stop_id === bus.current_stop_id);
  const stop2 = stops.find(s => s.stop_id === bus.next_stop_id);
  if (!stop1 || !stop2) return null;

  return {
    lat: stop1.lat + (stop2.lat - stop1.lat) * bus.progress,
    lng: stop1.lng + (stop2.lng - stop1.lng) * bus.progress,
  };
}

/**
 * Oblicza kierunek (azymut) autobusu w stopniach, potrzebny do obrotu ikony na mapie.
 */
export function getBearingForBus(
  bus: ActiveBus,
  stops: BusStop[]
): number {
  const s1 = stops.find(s => s.stop_id === bus.current_stop_id);
  const s2 = stops.find(s => s.stop_id === bus.next_stop_id);
  if (!s1 || !s2) return 0;

  const y = Math.sin((s2.lng - s1.lng) * Math.PI / 180) * Math.cos(s2.lat * Math.PI / 180);
  const x =
    Math.cos(s1.lat * Math.PI / 180) * Math.sin(s2.lat * Math.PI / 180) -
    Math.sin(s1.lat * Math.PI / 180) * Math.cos(s2.lat * Math.PI / 180) *
    Math.cos((s2.lng - s1.lng) * Math.PI / 180);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

/**
 * Zwraca etykietę czytelną dla service_type.
 */
export function serviceTypeLabel(type: string): string {
  if (type === 'GS') return 'Zawsze';
  if (type === 'S') return 'Szkolny';
  if (type === 'G') return 'Wolne';
  return type;
}
