
import { Article, WeatherData, TrafficStatus, Event, GUSStat } from './types';

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
