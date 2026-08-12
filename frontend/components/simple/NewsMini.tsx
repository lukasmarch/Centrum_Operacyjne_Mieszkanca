import React from 'react';
import { ArrowRight } from 'lucide-react';
import { Article } from '../../types';

interface NewsMiniProps {
    articles: Article[];
    onShowAll: () => void;
}

/**
 * 2–3 nagłówki z feedu + link do wszystkich. Bez zdjęć, bez kategorii,
 * bez chipów źródeł — w trybie prostym nagłówek i wiek wpisu wystarczą.
 *
 * Nagłówek prowadzi do feedu w serwisie, NIE do źródła. Wcześniej pierwsze
 * kliknięcie na stronie głównej wyrzucało gościa na Facebook albo do Radia 7
 * — czyli najczęstszy pierwszy gest nowego użytkownika kończył wizytę. Pełny
 * link do źródła stoi w feedzie i nikt go nie traci.
 */
const NewsMini: React.FC<NewsMiniProps> = ({ articles, onShowAll }) => (
    <section aria-label="Ostatnie wiadomości" className="rounded-2xl border border-white/10 bg-[#0d1117] p-5">
        <h3 className="text-lg font-bold text-white">Ostatnio w gminie</h3>
        <ul className="mt-3 divide-y divide-white/5">
            {articles.map(article => (
                <li key={article.id}>
                    <button onClick={onShowAll} className="group block w-full py-3 text-left">
                        <p className="text-base leading-snug text-neutral-200 transition-colors group-hover:text-white">
                            {article.title}
                        </p>
                        <p className="mt-1 text-xs text-neutral-500">{article.timestamp}</p>
                    </button>
                </li>
            ))}
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
