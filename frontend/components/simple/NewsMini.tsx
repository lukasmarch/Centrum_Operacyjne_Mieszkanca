import React from 'react';
import { Article } from '../../types';
import { EntrySquare, RowLink, Tag, boardOf } from './tv';

interface NewsMiniProps {
    articles: Article[];
    /** Pierwsze ładowanie — bez tego pusty kafel udawał „nic nowego w gminie” */
    loading?: boolean;
    onShowAll: () => void;
}

/**
 * 2–3 nagłówki z feedu + link do wszystkich.
 *
 * Nagłówek prowadzi do ŹRÓDŁA wpisu (decyzja Łukasza 21.10.2026: kto widzi
 * wiadomość i chce ją sprawdzić, nie ma lądować na ogólnej liście). Do 21.10
 * prowadził do feedu, bo kliknięcie wyrzucające gościa na Facebook kończyło
 * wizytę — dlatego źródło otwiera się w NOWEJ karcie, a serwis zostaje pod
 * spodem. Bez adresu wpisu nagłówek wraca do feedu.
 *
 * ⚠️ Miniatura stoi OBOK nagłówka, nigdy pod nim. Stary kafel wiadomości kładł
 * pierwszy tytuł na zdjęciu artykułu i to była najgorzej czytelna rzecz na całej
 * stronie — zdjęcie z terenu jest zwykle jasne i niejednorodne, więc biały tekst
 * gubi się w co drugim kadrze. Przyciągać ma kolor i obrazek, czytać się ma tekst
 * na jednolitym tle; te dwie rzeczy nie mogą dzielić tych samych pikseli.
 *
 * Zdjęcie ma dziś jeden wpis na cztery, więc miniatura NIE może zależeć od zdjęcia:
 * bez niego kwadrat pokazuje termin albo piktogram kategorii (`EntrySquare`).
 */
const NewsMini: React.FC<NewsMiniProps> = ({ articles, loading = false, onShowAll }) => (
    <section aria-label="Ostatnie wiadomości" className="flex flex-col">
        <Tag as="h2">Ostatnio w gminie</Tag>
        <div className="flex-1 border-t-2 border-tv-blue bg-tv-panel px-4 pb-1 lg:px-5">
            {loading && (
                <ul className="space-y-3 py-3" aria-hidden>
                    {[1, 2, 3].map(i => <li key={i} className="h-14 animate-pulse bg-tv-panel2" />)}
                </ul>
            )}
            {!loading && articles.length === 0 && (
                <p className="py-3 text-[16px] leading-snug text-tv-paper">
                    W ostatnich dniach nie pojawiło się nic nowego z gminy Rybno.
                    Wiadomości z okolicy są w pełnym feedzie.
                </p>
            )}
            <ul className="divide-y divide-tv-seam">
                {articles.map(article => (
                    <li key={article.id}>
                        <a
                            href={article.url || undefined}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={article.url ? undefined : e => { e.preventDefault(); onShowAll(); }}
                            className="group flex w-full items-start gap-3 py-3 text-left"
                        >
                            {/* 56 px: ikona kategorii czytelna, a nagłówkowi na telefonie
                                zostaje ponad 240 px. Miniatura OBOK tytułu, nigdy pod nim */}
                            {/* Zdjęcie → tablica z terminem w kolorze stanu → piktogram kategorii
                                (`EntrySquare`, ten sam co w Wiadomościach; krytyka 11.10.2026) */}
                            {(() => {
                                const board = boardOf(article);
                                return (
                                    <EntrySquare
                                        imageUrl={article.imageUrl}
                                        when={board.when}
                                        allDay={board.allDay}
                                        tone={board.tone}
                                        category={article.category}
                                        className="h-14 w-14"
                                    />
                                );
                            })()}
                            <span className="min-w-0 flex-1">
                                <span className="block text-[13px] text-tv-muted">
                                    <span className="font-bold text-tv-paper">{article.category}</span>
                                    {' · '}{article.timestamp}
                                </span>
                                {/* ⚠️ Bez `block`: `line-clamp-3` ustawia `display:-webkit-box` */}
                                <span className="mt-0.5 line-clamp-3 text-[16px] font-semibold leading-snug text-white group-hover:underline group-hover:underline-offset-4">
                                    {article.title}
                                </span>
                            </span>
                        </a>
                    </li>
                ))}
            </ul>
            <RowLink onClick={onShowAll}>Wszystkie wiadomości</RowLink>
        </div>
    </section>
);

export default NewsMini;
