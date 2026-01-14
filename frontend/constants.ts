
import { Article, WeatherData, TrafficStatus, Event, GUSStat, Stop, TimetableEntry } from './types';

export const MOCK_ARTICLES: Article[] = [
  {
    id: '1',
    title: 'Nowa inwestycja drogowa w gminie Rybno',
    summary: 'Rozpoczyna się modernizacja kluczowego odcinka drogi powiatowej. Prace potrwają do końca września.',
    source: 'Gmina Rybno',
    category: 'Infrastruktura',
    timestamp: '2h temu',
    url: '#',
    imageUrl: 'https://picsum.photos/seed/road/800/400'
  },
  {
    id: '2',
    title: 'Dni Działdowa 2024 - ogłoszono gwiazdy wieczoru',
    summary: 'W tym roku na scenie zobaczymy czołowych artystów polskiej estrady. Sprawdź pełny harmonogram.',
    source: 'Działdowo.pl',
    category: 'Kultura',
    timestamp: '4h temu',
    url: '#',
    imageUrl: 'https://picsum.photos/seed/concert/800/400'
  },
  {
    id: '3',
    title: 'Zmiany w komunikacji miejskiej od poniedziałku',
    summary: 'Nowe rozkłady jazdy linii numer 1 i 2. Urząd miasta wprowadza dodatkowe kursy poranne.',
    source: 'Moje Działdowo',
    category: 'Komunikacja',
    timestamp: '5h temu',
    url: '#',
    imageUrl: 'https://picsum.photos/seed/bus/800/400'
  }
];

export const MOCK_WEATHER: WeatherData = {
  temp: 22,
  condition: 'Słonecznie',
  humidity: 45,
  windSpeed: 12,
  lakeTemp: 19.5,
  lakeLevel: 'Stabilny'
};

export const MOCK_TRAFFIC: TrafficStatus[] = [
  { route: 'Działdowo - Rybno (DW538)', status: 'smooth', delayMinutes: 0 },
  { route: 'Centrum Działdowa', status: 'moderate', delayMinutes: 4 },
  { route: 'Wyjazd na Mławę (DK544)', status: 'heavy', delayMinutes: 12 }
];

export const MOCK_EVENTS: Event[] = [
  { id: 'e1', title: 'Piknik Rodzinny nad Jeziorem', date: 'Sobota, 14:00', location: 'Rybno', category: 'Rozrywka', isPromoted: true },
  { id: 'e2', title: 'Turniej Tenisa Stołowego', date: 'Niedziela, 10:00', location: 'Działdowo', category: 'Sport' },
  { id: 'e3', title: 'Kino pod Gwiazdami', date: 'Piątek, 21:00', location: 'Działdowo', category: 'Kino' }
];

export const MOCK_GUS_DATA: GUSStat[] = [
  { year: 2019, value: 62400, label: 'Ludność' },
  { year: 2020, value: 61900, label: 'Ludność' },
  { year: 2021, value: 61200, label: 'Ludność' },
  { year: 2022, value: 60500, label: 'Ludność' },
  { year: 2023, value: 59800, label: 'Ludność' }
];

// Bus Monitoring Constants
// Precise coordinates for stops along the route
export const STOPS: Stop[] = [
  { id: 'rybno', name: 'Rybno (Centrum)', lat: 53.3942, lng: 19.9392 },
  { id: 'tuczki_1', name: 'Tuczki I', lat: 53.3636, lng: 19.9767 },
  { id: 'tuczki_2', name: 'Tuczki II', lat: 53.3550, lng: 19.9850 },
  { id: 'zabiny', name: 'Żabiny', lat: 53.3456, lng: 19.9989 },
  { id: 'koszelewy', name: 'Koszelewy', lat: 53.3283, lng: 20.0319 },
  { id: 'plosnica', name: 'Płośnica', lat: 53.2797, lng: 20.1044 },
  { id: 'rutkowice', name: 'Rutkowice', lat: 53.2678, lng: 20.1339 },
  { id: 'skurpie_1', name: 'Skurpie I', lat: 53.2564, lng: 20.1581 },
  { id: 'skurpie_2', name: 'Skurpie II', lat: 53.2500, lng: 20.1650 },
  { id: 'burkat_1', name: 'Burkat I', lat: 53.2417, lng: 20.1786 },
  { id: 'burkat_2', name: 'Burkat II', lat: 53.2390, lng: 20.1790 },
  { id: 'dzialdowogrunwaldzka', name: 'Działdowo Grunwaldzka', lat: 53.2361, lng: 20.1803 },
  { id: 'dzialdowopkp', name: 'Działdowo PKP/PKS', lat: 53.2350, lng: 20.1830 },
];

const STOP_ORDER_RYB_DZA = ['rybno', 'tuczki_1', 'tuczki_2', 'zabiny', 'koszelewy', 'plosnica', 'rutkowice', 'skurpie_1', 'skurpie_2', 'burkat_1', 'burkat_2', 'dzialdowogrunwaldzka', 'dzialdowopkp'];
const STOP_ORDER_DZA_RYB = [...STOP_ORDER_RYB_DZA].reverse();

/**
 * Generates timetable entries with realistic time offsets for each stop.
 * Total trip duration is approximately 40 minutes.
 */
const createEntries = (startTimes: string[], order: string[], offsets: number[]): TimetableEntry[] => {
  return startTimes.map(time => {
    const [h, m] = time.split(':').map(Number);
    const stops: { [id: string]: string } = {};
    order.forEach((id, idx) => {
      // Calculate stop time based on start time + offset
      const totalMinutes = m + (offsets[idx] || 0);
      const stopH = (h + Math.floor(totalMinutes / 60)) % 24;
      const stopM = totalMinutes % 60;
      stops[id] = `${stopH.toString().padStart(2, '0')}:${stopM.toString().padStart(2, '0')}`;
    });
    return { departureTime: time, stops, type: 'GS' };
  });
};

// Travel offsets in minutes from the first stop
const RYB_DZA_OFFSETS = [0, 5, 7, 9, 13, 21, 25, 29, 31, 33, 35, 38, 40];
const DZA_RYB_OFFSETS = [0, 3, 5, 7, 10, 12, 15, 19, 27, 31, 33, 35, 40];

// Official hours from provided schedule
export const TIMETABLE_RYB_DZA = createEntries(
  ['06:40', '08:35', '10:45', '11:20', '13:00', '14:45', '15:15'],
  STOP_ORDER_RYB_DZA,
  RYB_DZA_OFFSETS
);

export const TIMETABLE_DZA_RYB = createEntries(
  ['07:25', '09:30', '11:40', '12:20', '13:50', '15:40', '16:20'],
  STOP_ORDER_DZA_RYB,
  DZA_RYB_OFFSETS
);
