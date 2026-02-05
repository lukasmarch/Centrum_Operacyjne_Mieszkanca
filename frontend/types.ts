
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
  imageUrl?: string;
  description?: string;
  externalUrl?: string;
}

export interface GUSStat {
  year: number;
  value: number;
  label: string;
}

export interface Business {
  id: number;
  ceidg_id: string;
  nazwa: string;
  nip: string;
  regon?: string;
  status: string;
  wlasciciel_imie?: string;
  wlasciciel_nazwisko?: string;
  ulica?: string;
  budynek?: string;
  miasto: string;
  kod_pocztowy: string;
  gmina: string;
  powiat: string;
  ceidg_link?: string;
  pkd_main?: string;
  pkd_list?: Array<{ kod: string; nazwa: string }>;
  branza?: string; // New mapped field
  adres_korespondencyjny?: Record<string, any>;
  spolki?: Array<Record<string, any>>;
  obywatelstwa?: Array<Record<string, any>>;
  email?: string;
  www?: string;
  telefon?: string;
}

export type AppSection = 'dashboard' | 'news' | 'events' | 'weather' | 'traffic' | 'stats' | 'business' | 'premium' | 'login' | 'register' | 'profile';

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

// Cinema Repertoire Types
export interface Movie {
  title: string;
  genre: string;
  time: string[];
  posterUrl: string;
  rating: string;
  link?: string;
}

export interface CinemaRepertoire {
  cinemaName: string;
  date: string;
  movies: Movie[];
}

export enum CinemaLocation {
  DZIALDOWO = 'Działdowo',
  LUBAWA = 'Lubawa'
}

// Auth Types (Sprint 1)
export type UserTier = 'free' | 'premium' | 'business';

export interface User {
  id: number;
  email: string;
  full_name: string;
  location: string;
  tier: UserTier;
  email_verified: boolean;
  preferences: Record<string, unknown> | null;
  created_at: string;
  last_login: string | null;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  full_name: string;
  location: string;
}

export interface UserUpdateData {
  full_name?: string;
  location?: string;
  preferences?: {
    categories?: string[];
    notifications?: Record<string, boolean>;
    newsletter_frequency?: 'none' | 'weekly' | 'daily';
  };
}

export const AVAILABLE_LOCATIONS = [
  'Rybno',
  'Działdowo',
  'Lubawa',
  'Lidzbark',
  'Iłowo-Osada',
  'Płośnica',
  'Kozłowo'
] as const;

export type AvailableLocation = typeof AVAILABLE_LOCATIONS[number];

// Waste Widget Types
export interface WasteEvent {
  type: string;
  originalDateString: string;
  daysRemaining: number;
}

export interface WasteSchedule {
  [town: string]: {
    [wasteType: string]: string;
  };
}
