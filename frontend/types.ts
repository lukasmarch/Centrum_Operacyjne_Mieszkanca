
export interface Article {
  id: string;
  title: string;
  summary: string;
  source: string;
  category: string;
  timestamp: string;
  url: string;
  imageUrl?: string;
}

export interface WeatherData {
  temp: number;
  condition: string;
  humidity: number;
  windSpeed: number;
  lakeTemp?: number;
  lakeLevel?: string;
  icon?: string;
}

export interface TrafficStatus {
  route: string;
  status: 'smooth' | 'moderate' | 'heavy';
  delayMinutes: number;
}

export interface Event {
  id: string;
  title: string;
  date: string;
  location: string;
  category: string;
  isPromoted?: boolean;
}

export interface GUSStat {
  year: number;
  value: number;
  label: string;
}

export type AppSection = 'dashboard' | 'news' | 'events' | 'weather' | 'traffic' | 'stats' | 'premium';

// New Traffic Widget Types
export enum TrafficCondition {
  FLUID = 'Płynnie',
  DIFFICULTIES = 'Utrudnienia',
  JAM = 'Korki',
  UNKNOWN = 'Brak danych'
}

export interface GroundingSource {
  title: string;
  uri: string;
}

export interface RoadStatus {
  id: string;
  name: string;
  status: TrafficCondition;
  delayMinutes: number;
  travelTime: string; // e.g., "25 min"
  description?: string;
}

export interface TrafficData {
  roads: RoadStatus[];
  lastUpdated: Date;
  sources?: GroundingSource[];
}

// Daily Summary Types
export interface DailySummaryEvent {
  title: string;
  date: string;
  location?: string;
}

export interface DailySummaryStats {
  total_articles: number;
  categories_count: number;
  events_count: number;
}

export interface DailySummary {
  date: string;
  headline: string;
  highlights: string[];
  summary_by_category: Record<string, string>;
  upcoming_events: DailySummaryEvent[];
  weather_summary: string;
  stats: DailySummaryStats;
}

// Bus Monitoring Types
export type Direction = 'RYBNO_DZIALDOWO' | 'DZIALDOWO_RYBNO';

export interface Stop {
  id: string;
  name: string;
  lat: number;
  lng: number;
}

export interface TimetableEntry {
  departureTime: string; // HH:mm
  stops: { [stopId: string]: string }; // stopId -> HH:mm
  type?: string;
}

export interface ActiveBus {
  direction: Direction;
  currentStopId: string;
  nextStopId: string;
  progress: number; // 0 to 1
  timeLeftMinutes: number;
  lastUpdate: Date;
}

export interface DirectionStatus {
  direction: Direction;
  isActive: boolean;
  activeBus?: ActiveBus;
  nextDeparture?: {
    time: string;
    inMinutes: number;
    from: string;
  };
}
