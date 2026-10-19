/**
 * „Gmina w kadrze" — własne zdjęcia gminy z podpisem (przewijana galeria).
 *
 * DLACZEGO TO ISTNIEJE: karta weekendowa opierała się wyłącznie na kalendarzu
 * wydarzeń, a kalendarz w gminie wiejskiej bywa pusty przez kilka tygodni.
 * Sekcja, której treść zależy od tego, czy ktoś coś zorganizował, przez pół
 * roku pokazuje wypełniacz. Zdjęcie z podpisem jest rubryką, którą kontrolujemy
 * sami — dlatego to ONO jest fundamentem karty, a wydarzenia dochodzą, gdy są.
 *
 * JAK DODAĆ WPIS:
 *  1. Wrzuć poziome zdjęcie do `frontend/public/simple/kadr/` (proporcje ~16:9,
 *     długi bok maks. 1600 px — `sips -Z 1600 plik.jpg`, jakość ~70).
 *     Zdjęcie musi być WŁASNE: kadry z portali i Facebooka są objęte prawami
 *     autorskimi i nie wolno ich tu podpinać.
 *  2. Dopisz wpis na POCZĄTEK tablicy — karta pokazuje je po kolei, od pierwszego.
 *  3. `date` w formacie ISO (RRRR-MM-DD) — pod spodem wyświetla się po polsku.
 *
 * Wpis może opisywać stan rzeczy, nie tylko widok: „remont drogi
 * Koszelewy–Tuczki, etap podbudowy" jest lepszą treścią niż ładny widok bez
 * informacji — mieszkaniec dostaje odpowiedź na pytanie, które i tak sobie zadaje.
 */

export interface PhotoPost {
    /** Ścieżka od katalogu `public`, np. `/simple/kadr/koszelewy-remont.jpg` */
    image: string;
    /** Krótki tytuł — to jest nagłówek karty */
    title: string;
    /** Dwa–trzy zdania. Konkret bije poetykę */
    description: string;
    /** RRRR-MM-DD */
    date: string;
    /** Autor zdjęcia, jeśli nie Twoje */
    credit?: string;
}

export const PHOTO_POSTS: PhotoPost[] = [
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-01.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-02.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-03.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-04.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-05.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-06.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-07.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-08.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-09.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-dron-2026-10-15-10.jpg',
        title: 'Gmina Rybno z lotu ptaka',
        description: 'Zdjęcie z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-koszelewy-2026-10-15.jpg',
        title: 'Koszelewy',
        description: 'Koszelewy z drona.',
        date: '2026-10-15',
    },
    {
        image: '/simple/kadr/rybno-zabiny-2026-10-15.jpg',
        title: 'Żabiny',
        description: 'Żabiny z drona.',
        date: '2026-10-15',
    },
];
