
export interface Article {
  id: string;
  title: string;
  summary: string;
  source: string;
  category: string;
  timestamp: string;
  rawTimestamp: string;
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

// Legacy GUS type (kept for backward compatibility)
export interface GUSStat {
  year: number;
  value: number;
  label: string;
}

// GUS Dashboard Types (Database-First Architecture)

export interface GUSVariableMetadata {
  key: string;
  var_id: string;
  name: string;
  unit: string;
  category: string;
  tier: UserTier;
  level: 'gmina' | 'powiat';
  format_type: 'integer' | 'decimal' | 'percentage' | 'currency';
}

export interface GUSVariableValue {
  value: number;
  year: number;
  trend_pct?: number; // Year-over-year change percentage
  historical?: GUSHistoricalData[]; // 10 years of historical data (added 2026-02-08)
  metadata: GUSVariableMetadata;
}

export interface GUSOverviewResponse {
  variables: Record<string, GUSVariableValue>;
  user_tier: UserTier;
  last_refresh: string;
}

export interface GUSHistoricalData {
  year: number;
  value: number;
}

export interface GUSComparison {
  unit_name: string;
  unit_id: string;
  value: number;
  year: number;
}

export interface GUSNationalComparison {
  national_value: number;
  gmina_value: number;
  percentage_of_national: number;
  year: number;
}

// Powiat comparison (gmina vs powiat Działdowski) - added 2026-02-08
export interface GUSPowiatComparison {
  powiat_value: number;
  gmina_value: number;
  percentage_of_powiat: number;
  difference: number;
  year: number;
}

export interface GUSSectionVariable {
  current: GUSVariableValue;
  trend: GUSHistoricalData[];
  comparison: GUSComparison[];
  national_comparison?: GUSNationalComparison; // legacy, deprecated
  powiat_comparison?: GUSPowiatComparison; // new: gmina vs powiat
}

export interface GUSSectionResponse {
  section_key: string;
  section_name: string;
  variables: Record<string, GUSSectionVariable>;
  user_tier: UserTier;
  last_refresh: string;
}

export interface GUSVariableDetailResponse {
  variable: GUSVariableMetadata;
  current: {
    value: number;
    year: number;
    trend_pct?: number;
  };
  historical_trend: GUSHistoricalData[];
  comparison_gminy: GUSComparison[];
  national_comparison?: GUSNationalComparison;
  last_refresh: string;
}

export interface GUSCategory {
  key: string;
  name: string;
  description: string;
  variable_count: number;
  required_tier: UserTier;
}

export interface GUSCategoriesResponse {
  categories: GUSCategory[];
  user_tier: UserTier;
}

export interface GUSVariableListItem {
  key: string;
  var_id: string;
  name: string;
  unit: string;
  category: string;
  tier: UserTier;
  level: 'gmina' | 'powiat';
}

export interface GUSVariablesListResponse {
  variables: GUSVariableListItem[];
  user_tier: UserTier;
  total_count: number;
  tier_counts: {
    free: number;
    premium: number;
    business: number;
  };
}

export interface GUSFreshnessEntry {
  category: string;
  variable_count: number;
  last_refresh: string;
  next_scheduled_refresh: string;
}

export interface GUSFreshnessResponse {
  freshness: GUSFreshnessEntry[];
  last_global_refresh: string;
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
  lokal?: string;
  miasto: string;
  kod_pocztowy: string;
  gmina: string;
  powiat: string;
  ceidg_link?: string;
  pkd_main?: string;
  pkd_list?: Array<{ kod: string; nazwa: string }>;
  branza?: string; // UI-friendly category from PKD_FRIENDLY_NAMES
  data_rozpoczecia?: string; // ISO datetime string – year founded
  adres_korespondencyjny?: Record<string, any>;
  spolki?: Array<Record<string, any>>;
  obywatelstwa?: Array<Record<string, any>>;
  email?: string;
  www?: string;
  telefon?: string;
}

// Zgłoszenie24 – Citizen Reports
export type ReportStatus = 'new' | 'verified' | 'in_progress' | 'resolved' | 'rejected';
export type ReportCategory = 'emergency' | 'fire' | 'infrastructure' | 'waste' | 'greenery' | 'safety' | 'water' | 'other';
export type ReportSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface Report {
  id: number;
  title: string;
  description: string;
  ai_summary?: string;
  category: ReportCategory;
  ai_detected_objects?: Record<string, any>;
  ai_condition_assessment?: string;
  ai_severity?: ReportSeverity;
  image_url?: string;
  generated_image_url?: string;
  latitude?: number;
  longitude?: number;
  address?: string;
  location_name?: string;
  status: ReportStatus;
  is_spam: boolean;
  upvotes: number;
  views_count: number;
  author_name?: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
}

export interface ReportListResponse {
  reports: Report[];
  total: number;
  page: number;
  limit: number;
}

export interface ReportMapItem {
  id: number;
  title: string;
  category: ReportCategory;
  ai_severity?: ReportSeverity;
  latitude: number;
  longitude: number;
  status: string;
  upvotes: number;
  image_url?: string;
  created_at: string;
}

export type AppSection = 'dashboard' | 'news' | 'events' | 'weather' | 'traffic' | 'stats' | 'business' | 'reports' | 'premium' | 'assistant' | 'login' | 'register' | 'profile';

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
  highlights: string;
  summary_by_category: Record<string, string>;
  upcoming_events: string[];
  air_quality_summary?: string;
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
