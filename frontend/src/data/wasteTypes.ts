export interface WasteSchedule {
  [townName: string]: {
    [wasteType: string]: string; // comma separated dates
  };
}

export interface WasteEvent {
  type: string;
  date: Date;
  daysRemaining: number;
  originalDateString: string;
}

export interface UserProfile {
  name: string;
  town: string;
  avatar: string;
}
