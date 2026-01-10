
export enum TrafficStatus {
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
  status: TrafficStatus;
  delayMinutes: number;
  travelTime: string; // e.g., "25 min"
  description?: string;
}

export interface TrafficData {
  roads: RoadStatus[];
  lastUpdated: Date;
  sources?: GroundingSource[];
}
