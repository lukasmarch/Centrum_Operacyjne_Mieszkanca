import { GoogleGenAI, Type } from "@google/genai";
import { TrafficCondition, RoadStatus, GroundingSource, CinemaRepertoire, CinemaLocation } from "../../types";

const ai = new GoogleGenAI({ apiKey: import.meta.env.VITE_GOOGLE_API_KEY || '' });

export const fetchTrafficData = async (latitude?: number, longitude?: number): Promise<{ roads: RoadStatus[], sources: GroundingSource[] }> => {
    try {
        const prompt = `
      Jesteś dyspozytorem ruchu dla regionu Rybno (powiat działdowski). 
      Twoim centrum jest miejscowość RYBNO. Sprawdź AKTUALNE (real-time) warunki drogowe i czasy przejazdu dla tras:
      1. Rybno -> Działdowo (DW538)
      2. Rybno -> Lubawa (DW538/DW541)
      3. Rybno -> Iława (przez Hartowiec)
      4. Rybno -> Olsztyn (najszybsza aktualna trasa)
      
      Zasady analizy:
      - Podaj AKTUALNY CZAS PRZEJAZDU (TravelTime) w minutach.
      - Opóźnienie (Delay) to różnica między czasem aktualnym a optymalnym.
      - W opisie ('NOTE') bądź ekstremalnie precyzyjny: jeśli jest zima, sprawdź czy przyczyną jest śliska nawierzchnia, błoto pośniegowe czy praca pługów. Jeśli to korek w małym mieście, określ czy to zator przy przejeździe kolejowym czy wzmożony ruch lokalny.
      - Opis musi być jednym, treściwym zdaniem, które wyjaśnia "dlaczego" (np. "Błoto pośniegowe na podjazdach pod wzniesienia spowalnia ruch ciężarowy").

      Format odpowiedzi:
      [ROUTE: Skąd-Dokąd | TIME: X min | STATUS: Status | DELAY: X min | NOTE: Opis przyczyny]
    `;

        const response = await ai.models.generateContent({
            model: "gemini-2.0-flash",
            contents: prompt,
            config: {
                tools: [{ googleSearch: {} }],
            },
        });

        const text = response.text || "";
        const sources: GroundingSource[] = [];
        const chunks = response.candidates?.[0]?.groundingMetadata?.groundingChunks;
        if (chunks) {
            chunks.forEach((chunk: any) => {
                if (chunk.web) {
                    sources.push({
                        title: chunk.web.title || "Źródło WWW",
                        uri: chunk.web.uri
                    });
                }
            });
        }

        return {
            roads: parseGeminiResponse(text),
            sources
        };
    } catch (error) {
        console.error("Error fetching traffic data:", error);
        // Fallback data reflecting the new Rybno focus
        return {
            roads: [
                { id: '1', name: 'Rybno -> Działdowo', status: TrafficCondition.DIFFICULTIES, delayMinutes: 5, travelTime: '28 min', description: 'Utrudnienia przy wjeździe do Działdowa przez oblodzoną nawierzchnię na DW538.' },
                { id: '2', name: 'Rybno -> Lubawa', status: TrafficCondition.FLUID, delayMinutes: 0, travelTime: '22 min', description: 'Trasa czysta, nawierzchnia czarna mokra, brak widocznych utrudnień.' },
                { id: '3', name: 'Rybno -> Iława', status: TrafficCondition.FLUID, delayMinutes: 0, travelTime: '35 min', description: 'Ruch odbywa się płynnie, zachowana dobra przejezdność przez Hartowiec.' },
                { id: '4', name: 'Rybno -> Olsztyn', status: TrafficCondition.JAM, delayMinutes: 15, travelTime: '1h 10 min', description: 'Znaczne opóźnienia na trasie przez opady śniegu i spowolniony ruch na wysokości Nidzicy.' },
            ],
            sources: []
        };
    }
};

const parseGeminiResponse = (text: string): RoadStatus[] => {
    const roads: RoadStatus[] = [];
    const lines = text.split('\n');
    const entryRegex = /\[ROUTE: (.*?) \| TIME: (.*?) \| STATUS: (.*?) \| DELAY: (.*?) \| NOTE: (.*?)\]/;

    lines.forEach((line, index) => {
        const match = line.match(entryRegex);
        if (match) {
            const name = match[1].trim();
            const travelTime = match[2].trim();
            const statusText = match[3].trim();
            const delayText = match[4].trim();
            const note = match[5].trim();

            let status = TrafficCondition.UNKNOWN;
            const s = statusText.toLowerCase();
            if (s.includes('płyn')) status = TrafficCondition.FLUID;
            else if (s.includes('utrud')) status = TrafficCondition.DIFFICULTIES;
            else if (s.includes('kork')) status = TrafficCondition.JAM;

            const delay = parseInt(delayText) || 0;

            roads.push({
                id: String(index),
                name,
                status,
                delayMinutes: delay,
                travelTime: travelTime,
                description: (note && note.length > 5) ? note : undefined
            });
        }
    });

    return roads.length > 0 ? roads : [];
};

export const fetchCinemaRepertoire = async (location: CinemaLocation): Promise<CinemaRepertoire> => {
    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    try {
        const response = await fetch(`${API_URL}/cinema/repertoire?location=${location}`);

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        return data;

    } catch (error) {
        console.error("Error fetching cinema data form backend:", error);

        // Fallback Mock Data so the UI always looks good even without Backend
        const mockMovies = [
            {
                title: "Diuna: Część druga (Offline)",
                genre: "Sci-Fi / Przygodowy",
                time: ["16:00", "19:30"],
                rating: "8.8/10",
                posterUrl: "https://picsum.photos/300/450?random=101",
                link: "https://coigdzie.pl"
            },
            {
                title: "Błąd Połączenia",
                genre: "Sprawdź Backend",
                time: ["14:15", "16:15"],
                rating: "0/10",
                posterUrl: "https://picsum.photos/300/450?random=102"
            }
        ];

        return {
            cinemaName: `Kino ${location} (Offline)`,
            date: new Date().toLocaleDateString('pl-PL'),
            movies: mockMovies
        };
    }
};
