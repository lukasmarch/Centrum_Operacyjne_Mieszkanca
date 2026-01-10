
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
