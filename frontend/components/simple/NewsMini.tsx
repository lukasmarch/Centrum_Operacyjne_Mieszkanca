import React from 'react';
import { ArrowRight } from 'lucide-react';
import { Article } from '../../types';
import ArticleImage, { getCategoryTheme } from '../ArticleImage';

interface NewsMiniProps {
    articles: Article[];
    onShowAll: () => void;
}

/**
 * 2–3 nagłówki z feedu + link do wszystkich.
 *
 * Nagłówek prowadzi do feedu w serwisie, NIE do źródła. Wcześniej pierwsze
 * kliknięcie na stronie głównej wyrzucało gościa na Facebook albo do Radia 7
 * — czyli najczęstszy pierwszy gest nowego użytkownika kończył wizytę. Pełny
 * link do źródła stoi w feedzie i nikt go nie traci.
 *
 * ⚠️ Miniatura stoi OBOK nagłówka, nigdy pod nim. Stary kafel wiadomości kładł
 * pierwszy tytuł na zdjęciu artykułu i to była najgorzej czytelna rzecz na całej
 * stronie — zdjęcie z terenu jest zwykle jasne i niejednorodne, więc biały tekst
 * gubi się w co drugim kadrze. Przyciągać ma kolor i obrazek, czytać się ma tekst
 * na jednolitym tle; te dwie rzeczy nie mogą dzielić tych samych pikseli.
 *
 * Zdjęcie ma dziś jeden wpis na cztery, więc miniatura NIE może zależeć od zdjęcia:
 * `ArticleImage` podstawia gradient z ikoną kategorii i lista zostaje równa.
 */
const NewsMini: React.FC<NewsMiniProps> = ({ articles, onShowAll }) => (
    <section aria-label="Ostatnie wiadomości" className="rounded-2xl border border-white/10 bg-[#0d1117] p-5">
        <h3 className="text-lg font-bold text-white">Ostatnio w gminie</h3>
        <ul className="mt-3 divide-y divide-white/5">
            {articles.map(article => {
                const theme = getCategoryTheme(article.category);
                return (
                    <li key={article.id}>
                        <button onClick={onShowAll} className="group flex w-full items-start gap-3 py-3 text-left">
                            {/* 56 px: duże na tyle, żeby ikona kategorii była czytelna,
                                małe na tyle, żeby nagłówkowi na telefonie zostało
                                ponad 240 px — czyli około 28 znaków w wierszu */}
                            <span className="h-14 w-14 shrink-0 overflow-hidden rounded-xl border border-white/10">
                                <ArticleImage
                                    imageUrl={article.imageUrl}
                                    category={article.category}
                                    iconSize="sm"
                                />
                            </span>

                            <span className="min-w-0 flex-1">
                                {/* Kategoria i wiek w JEDNYM wierszu — osobna plakietka
                                    nad tytułem kosztowałaby trzeci wiersz w kafelku,
                                    w którym i tak walczymy o miejsce */}
                                <span className="flex flex-wrap items-center gap-x-2 text-[11px] font-bold uppercase tracking-wider">
                                    <span className={`rounded px-1.5 py-0.5 ${theme.badge} border`}>
                                        {article.category}
                                    </span>
                                    <span className="font-medium normal-case tracking-normal text-neutral-500">
                                        {article.timestamp}
                                    </span>
                                </span>
                                {/* Rozmiar nagłówka bez zmian (16 px). Miniatura zabrała
                                    szerokość, więc kusiło, żeby zejść do 14 px — ale to
                                    właśnie ten tekst mieszkaniec ma przeczytać na telefonie.
                                    Trzy wiersze wystarczą na najdłuższe nagłówki AI,
                                    a przycięcie chroni rytm listy */}
                                {/* ⚠️ Bez `block`: `line-clamp-3` ustawia `display:-webkit-box`,
                                    a klasa `block` wygrywa w arkuszu i wycina przycinanie
                                    po cichu — tekst leci wtedy na cztery i pięć wierszy */}
                                <span className="mt-1 line-clamp-3 text-base font-medium leading-snug text-neutral-100 transition-colors group-hover:text-white">
                                    {article.title}
                                </span>
                            </span>
                        </button>
                    </li>
                );
            })}
        </ul>
        <button
            onClick={onShowAll}
            className="mt-2 flex min-h-[44px] items-center gap-1.5 text-sm font-semibold text-blue-400 transition-colors hover:text-blue-300"
        >
            Wszystkie wiadomości
            <ArrowRight size={15} aria-hidden />
        </button>
    </section>
);

export default NewsMini;
