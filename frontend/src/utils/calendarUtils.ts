
import { NAMEDAYS } from '../data/namedays';

export const getEasterDate = (year: number): Date => {
    const a = year % 19;
    const b = Math.floor(year / 100);
    const c = year % 100;
    const d = Math.floor(b / 4);
    const e = b % 4;
    const f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const i = Math.floor(c / 4);
    const k = c % 4;
    const l = (32 + 2 * e + 2 * i - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const p = h + l - 7 * m + 114;
    const month = Math.floor(p / 31) - 1; // 0-indexed month
    const day = p % 31 + 1;
    return new Date(year, month, day);
};

export const addDays = (date: Date, days: number): Date => {
    const result = new Date(date);
    result.setDate(result.getDate() + days);
    return result;
};

export const getMovableHolidays = (year: number): Record<string, string> => {
    const easter = getEasterDate(year);
    const fatThursday = addDays(easter, -52);
    const ashWednesday = addDays(easter, -46);
    const palmSunday = addDays(easter, -7);
    const goodFriday = addDays(easter, -2);
    const easterMonday = addDays(easter, 1);
    const pentecost = addDays(easter, 49);
    const corpusChristi = addDays(easter, 60);

    const formatDate = (d: Date) => `${d.getMonth() + 1}-${d.getDate()}`;

    return {
        [formatDate(fatThursday)]: "Tłusty Czwartek",
        [formatDate(ashWednesday)]: "Środa Popielcowa",
        [formatDate(palmSunday)]: "Niedziela Palmowa",
        [formatDate(goodFriday)]: "Wielki Piątek",
        [formatDate(easter)]: "Wielkanoc",
        [formatDate(easterMonday)]: "Poniedziałek Wielkanocny",
        [formatDate(pentecost)]: "Zielone Świątki",
        [formatDate(corpusChristi)]: "Boże Ciało",
    };
};

export const FIXED_HOLIDAYS: Record<string, string> = {
    "1-8": "Dzień Sprzątania Biurka",
    "1-18": "Dzień Bałwana",
    "1-20": "Dzień Pingwinów",
    "1-21": "Dzień doceniania wiewiórek / Dzień Babci i Dzień Dziadka",
    "1-23": "Dzień Bez Opakowań Foliowych",
    "1-27": "Dzień Pamięci o Ofiarach Holocaustu",
    "1-31": "Dzien Zebry",
    "2-1": "Dzień bez oleju palmowego",
    "2-2": "Dzień Mokradeł",
    "2-6": "Międzynarodowy Dzień Zerowej Tolerancji dla Okaleczania Żeńskich Narządów Płciowych",
    "2-11": "Dzień Kobiet i Dziewcząt w Nauce / Dzień Dokarmiania Zwierzyny Leśnej",
    "2-12": "Dzień Dzieci-Żołnierzy / Dzień Darwina",
    "2-14": "Dzień Uzdrawiania Dźwiękiem / Walentynki",
    "2-15": "Dzień Wielorybów",
    "2-16": "Dzień Listonoszy i Doręczycieli Przesyłek Pocztowych",
    "2-17": "Dzień Kota",
    "2-18": "Dzień Baterii",
    "2-20": "Światowy Dzień Sprawiedliwości Społecznej",
    "2-21": "Dzień Języka Ojczystego / Dzień Sprzeciwu Wobec Reżimu Kolonialnego",
    "2-27": "Dzień Niedźwiedzia Polarnego / Dzień Organizacji Społecznych",
    "3-1": "Dzień Walki Przeciw Zbrojeniom Atomowym / Dzień Obrony Cywilnej",
    "3-3": "Dzień Środowiska Afrykańskiego / Dzień Dzikiej Przyrody / Europejski Dzień Równych Płac / Dzień Wangari Maathai",
    "3-8": "Dzień Kobiet",
    "3-14": "Dzień liczby Pi",
    "3-15": "Światowy Dzień Praw Konsumenta",
    "3-20": "Dzień Wróbla / Światowy Dnia Inwalidów i Osób z Niepełnosprawnościami / Dzień Szczęścia / Międzynarodowy Dzień Nowruz / Dzień bez Mięsa",
    "3-21": "Światowy Dzień Poezji / Dzień Lasów / Pierwszy Dzień Wiosny / Dzień Walki z Rasizmem / Dzień Kolorowej Skarpetki / Dzień Wierzby",
    "3-22": "Światowy Dzień Wody",
    "3-23": "Dzień Meteorologii",
    "3-24": "Dzień Prawa do Prawdy dotyczącej Poważnych Naruszeń Praw Człowieka i Godności Ofiar",
    "3-25": "Dzień Pamięci Ofiar Niewolnictwa i Transatlantyckiego Handlu Niewolnikami",
    "3-27": "Międzynarodowy Dzień Teatru",
    "3-28": "Dzień Chwastów",
    "3-29": "Dzień Uznania dla Manatów",
    "3-30": "Dzień Świadomości o Kleszczowym Zapaleniu Mózgu",
    "4-1": "Dzień Ptaków",
    "4-2": "Dzień Książki dla Dzieci",
    "4-4": "Dzień Zwierząt Bezdomnych",
    "4-5": "Dzień Leśnika i Drzewiarza",
    "4-7": "Dzień Bobrów / Światowy Dzień Zdrowia",
    "4-12": "Międzynarodowy Dzień Dzieci Ulicy / Światowy Dzień Czekolady",
    "4-14": "Dzień Gapienia się w Niebo",
    "4-16": "Dzień Ochrony Słoni",
    "4-18": "Międzynarodowy Dzień Ochrony Zabytków",
    "4-20": "Międzynarodowy Dzień Wolnej Prasy",
    "4-21": "Eid al-Fitr",
    "4-22": "Dzień Ziemi",
    "4-23": "Światowy Dzień Książki",
    "4-24": "Dzień Zwierząt Laboratoryjnych",
    "4-25": "Dzień Świadomości Zagrożenia Hałasem / Dzień Walki z Malarią",
    "4-27": "Dzień Lekarzy Weterynarii",
    "4-28": "Dzień Bezpieczeństwa i Ochrony Zdrowia w Pracy",
    "4-30": "Dzień Sprzeciwu wobec Bicia Dzieci",
    "5-1": "Święto Pracy",
    "5-2": "Dzień Tuńczyka",
    "5-3": "Dzień Bez Komputera",
    "5-4": "Międzynarodowy Dzień Strażaka",
    "5-5": "Dzień Walki z Dyskryminacją Osób Niepełnosprawnych",
    "5-8": "Dzień Czerwonego Krzyża / Dzień Bibliotek",
    "5-9": "Dzień Sprawiedliwego Handlu",
    "5-10": "Dzień Drzewa Arganowego",
    "5-11": "Dzień bez śmiecenia",
    "5-12": "Dzień Ptaków Wędrownych",
    "5-15": "Międzynarodowy Dzień Rodzin / Dzień Polskiej Niezapominajki",
    "5-16": "Dzień siania dyni w miejscach publicznych",
    "5-17": "Dzień Walki z Homofobią",
    "5-19": "Dzień Dobrych Uczynków",
    "5-20": "Światowy Dzień Pszczół",
    "5-21": "Światowy Dzień Kosmosu / Dzień Różnorodności Kulturowej na rzecz Dialogu i Rozwoju",
    "5-22": "Dzień Różnorodności Biologicznej",
    "5-23": "Dzień Żółwia",
    "5-24": "Dzień Parków Narodowych",
    "5-25": "Dzień Afryki",
    "5-26": "Dzień Matki",
    "5-27": "Dzień Sąsiada",
    "5-29": "Dzień Świadomości Wydry",
    "5-31": "Dzień Bociana Białego",
    "6-1": "Dzień Dziecka",
    "6-3": "Dzień Roweru",
    "6-4": "Dzień Dzieci Będących Ofiarami Agresji",
    "6-5": "Dzień Ochrony Środowiska",
    "6-8": "Dzień Lalki / Dzień Oceanów / Dzień Cyrku bez Zwierząt",
    "6-12": "Dzień Sprzeciwu Wobec Pracy Dzieci",
    "6-14": "Dzień Pustej Klasy",
    "6-15": "Dzień Wiatru",
    "6-16": "Dzień Dziecka Afrykańskiego",
    "6-17": "Dzień Przeciwdziałania Pustynnieniu i Suszy",
    "6-18": "Dzień Protestu Przeciwko GMO",
    "6-19": "Dzień Leniwych Spacerów",
    "6-20": "Światowy Dzień Uchodźcy",
    "6-21": "Światowy Dzień Żyrafy / Noc Kupały",
    "6-23": "Dzień Ojca / Dzien Wdów",
    "6-26": "Dzień Pomocy Ofiarom Tortur",
    "6-27": "Dzień Rybołówstwa",
    "6-30": "Dzień Motyla Kapustnika",
    "7-1": "Dzień Architektury / Dzień Psa",
    "7-4": "Dzień Wypadów do Parku",
    "7-11": "Światowy Dzień Ludności",
    "7-15": "Dzień bez Telefonu Komórkowego",
    "7-18": "Światowy Dzień Słuchania / Dzień Nelsona Mandeli",
    "7-26": "Dzień Ochrony Ekosystemów Namorzynowych",
    "7-29": "Dzień Tygrysa / Dzień Długu Ekologicznego",
    "8-8": "Wielki Dzień Pszczół",
    "8-9": "Dzień Ludności Rdzennej",
    "8-19": "Dzień Pomocy Humanitarnej",
    "8-20": "Światowy Dzień Komara",
    "8-23": "Międzynarodowy Dzień Pamięci o Handlu Niewolnikami i jego Zniesieniu",
    "8-25": "Międzynarodowa Noc Nietoperzy",
    "8-29": "Dzień Sprzeciwu Wobec Prób Jądrowych",
    "9-8": "Międzynarodowy Dzień Alfabetyzacji",
    "9-11": "Dzień Łosia",
    "9-12": "Dzień na rzecz Współpracy Południe–Południe",
    "9-15": "Dzień Demokracji",
    "9-17": "Dzień Solidarności z pracownicami fabryk odzieżowych w Kambodży",
    "9-19": "Park(ing) Day / Dzień Dzikiej Fauny, Flory i Naturalnych Siedlisk",
    "9-21": "Dzień Pokoju",
    "9-22": "Dzień Bez Samochodu / Dożynki",
    "9-27": "Światowy Dzień Turystyki / Dzień Rzek",
    "9-28": "Dzień Mórz / Światowy Dzień Mórz",
    "9-29": "Dzień Kuriera i Przewoźnika / Międzynarodowy Dzień Kawy / Dzień Świadomości o Marnowaniu Żywności",
    "10-1": "Dzień Wegetarianizmu / Dzień Osób Starszych",
    "10-2": "Dzień Empatii / Dzień Zwierząt Hodowlanych / Międzynarodowy Dzień bez Przemocy",
    "10-4": "Światowy Dzień Zwierząt",
    "10-6": "Światowy Dzień Mieszkalnictwa",
    "10-7": "Dzień Godnej Płacy",
    "10-10": "Dzień Sprzeciwu Wobec Kary Śmierci / Święto Drzewa",
    "10-13": "Dzień Zmniejszania Skutków Klęsk Żywiołowych",
    "10-14": "Dzień Edukacji Narodowej",
    "10-15": "Dzień Kobiet Wiejskich / Dzień Mycia Rąk",
    "10-16": "Światowy Dzień Żywności",
    "10-17": "Dzień Walki z Ubóstwem",
    "10-24": "Dzień Kundelka / Dzień Informacji o Rozwoju / Dzień NZ",
    "10-28": "Dzień Odpoczynku dla Zszarganych Nerwów",
    "10-31": "Dzień Miast",
    "11-1": "Dzień Weganizmu / Wszystkich Świętych",
    "11-2": "Dzień Zaduszny",
    "11-6": "Dzień Zapobiegania Wyzyskowi Środowiska Naturalnego podczas Wojen",
    "11-10": "Dzień Jeża / Dzień Nauki dla Pokoju i Rozwoju",
    "11-11": "Światowy Dzień Niepodległości",
    "11-14": "Dzień Czystego Powietrza",
    "11-16": "Dzień Tolerancji",
    "11-17": "Tydzień Edukacji Globalnej",
    "11-18": "Dzień Wiedzy o Antybiotykach",
    "11-19": "Dzień Toalet / Dzień Zapobiegania Przemocy Wobec Dzieci",
    "11-20": "Dzień Uprzemysłowienia Afryki / Dzień Praw Dziecka",
    "11-21": "Dzień Życzliwosci",
    "11-24": "Katarzynki",
    "11-25": "Dzień Kolejarza i Tramwajarza / Dzień bez Futra / Dzień Pluszowego Misia",
    "11-28": "Dzień bez kupowania",
    "11-29": "Andrzejki",
    "12-1": "Światowy Dzień Walki z AIDS",
    "12-2": "Dzień Upamiętniający Zniesienie Niewolnictwa",
    "12-3": "Dzień Osób Niepełnosprawnych",
    "12-4": "Barbórka",
    "12-5": "Dzień Wolontariusza / Dzień Gleb",
    "12-6": "Mikołajki",
    "12-7": "Dzień Teatrzyku Kamishibai / Dzień Lotnictwa Cywilnego",
    "12-10": "Dzień Praw Człowieka",
    "12-11": "Dzień Terenów Górskich",
    "12-14": "Dzień Małpy",
    "12-18": "Chanuka",
    "12-20": "Dzień Ryby / Dzień Solidarności",
    "12-24": "Wigilia",
    "12-31": "Sylwester",
};

export const getHoliday = (date: Date): string | null => {
    const dayKey = `${date.getMonth() + 1}-${date.getDate()}`;
    const year = date.getFullYear();

    if (FIXED_HOLIDAYS[dayKey]) {
        return FIXED_HOLIDAYS[dayKey];
    }

    const movableHolidays = getMovableHolidays(year);
    if (movableHolidays[dayKey]) {
        return movableHolidays[dayKey];
    }

    return null;
};

export const getNameDays = (date: Date): string => {
    const dayKey = `${date.getMonth() + 1}-${date.getDate()}`;
    const names = NAMEDAYS[dayKey];
    if (names && names.length > 0) {
        return names.join(", ");
    }
    return "";
};
