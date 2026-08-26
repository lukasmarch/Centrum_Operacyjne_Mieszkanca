import React, { useMemo } from 'react';
import { Landmark, ChevronRight } from 'lucide-react';
import { useEvents } from '../../src/hooks/useEvents';
import { useCouncilSessions } from '../../src/hooks/useCouncil';
import { phaseOf, upcomingFirst } from '../../src/utils/eventTime';

interface CouncilCardProps {
    onClick: () => void;
}

/**
 * „Rada Gminy" — jeden kafel na dwa stany, żeby nie był martwy przez jedenaście
 * miesięcy w roku.
 *
 * Sesja zdarza się ~raz w miesiącu. Kafel pokazujący wyłącznie „dziś sesja"
 * przez resztę czasu byłby pustym polem, a puste pole uczy mieszkańca, że
 * w tym miejscu nic nie ma, i przestaje być klikane (to samo rozumowanie,
 * co w `CinemaCard`, tylko rozwiązane odwrotnie — kino ma czym się schować,
 * Rada nie).
 *
 * Dlatego kafel patrzy w dwie strony:
 *  • **przed sesją** — termin z kalendarza, co jest w porządku obrad i ile
 *    trwały poprzednie obrady (mieszkaniec pyta „ile to potrwa", zanim
 *    zdecyduje, czy iść albo oglądać);
 *  • **poza sesją** — nagłówek ostatniego skrótu, czyli „co ostatnio ustalono".
 *
 * Znika tylko wtedy, gdy nie ma ANI zapowiedzi, ANI żadnego skrótu — czyli
 * w stanie, w którym naprawdę nie ma o czym mówić.
 */

/** Posiedzenie komisji to nie sesja — kafel mówi o obradach Rady w komplecie. */
const SESSION_TITLE = /sesja\s+rady/i;

const MONTHS = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca',
    'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];

function dayWord(date: Date, now: Date): string {
    if (date.toDateString() === now.toDateString()) return 'dziś';
    const tomorrow = new Date(now);
    tomorrow.setDate(now.getDate() + 1);
    if (date.toDateString() === tomorrow.toDateString()) return 'jutro';
    return `${date.getDate()} ${MONTHS[date.getMonth()]}`;
}

/**
 * Z ogłoszenia o sesji zostaw to, czego nie ma nad spodem kafla.
 *
 * Opis z BIP zaczyna się zawsze od zdania „XXIV sesja … odbędzie się 27 sierpnia
 * o godz. 10:00 w sali sesyjnej…", a termin i miejsce stoją już w nadtytule
 * i w tytule kafla. Powtórzone zjadają jedyne dwie linijki, w których można
 * powiedzieć, PO CO ta sesja — a to jest cała informacja, po której mieszkaniec
 * decyduje, czy go to dotyczy.
 */
const AGENDA_OPENERS = /(W\s+programie|W\s+porz[ąa]dku\s+obrad|Program\s+obejmuje|Tematyka|W\s+planie)/i;

function agendaOf(details?: string, fallback?: string): string | undefined {
    if (!details) return fallback;
    const at = details.search(AGENDA_OPENERS);
    return at >= 0 ? details.slice(at).trim() : fallback;
}

function dateLabel(iso: string | null): string {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    if (!y || !m || !d) return iso;
    return `${d} ${MONTHS[m - 1]}`;
}

const CouncilCard: React.FC<CouncilCardProps> = ({ onClick }) => {
    const { events } = useEvents();
    const { sessions } = useCouncilSessions();

    /** Najbliższa sesja Rady z kalendarza — komisje pomijamy. */
    const next = useMemo(() => {
        const upcoming = upcomingFirst(events).filter(e => SESSION_TITLE.test(e.title));
        return upcoming[0] ?? null;
    }, [events]);

    /**
     * Ile trwały poprzednie obrady. Przy jednej sesji mówimy o niej wprost —
     * „średnio" przy jednym pomiarze to nadęcie, które czytelnik wyczuwa.
     */
    const duration = useMemo(() => {
        const minutes = (sessions ?? [])
            .map(s => s.duration_min)
            .filter((m): m is number => typeof m === 'number' && m > 0);
        if (!minutes.length) return null;
        if (minutes.length === 1) return `Poprzednie obrady trwały ${minutes[0]} minut.`;
        const avg = Math.round(minutes.reduce((a, b) => a + b, 0) / minutes.length);
        return `Poprzednie obrady trwały średnio ${avg} minut.`;
    }, [sessions]);

    const latest = sessions?.[0] ?? null;

    if (!next && !latest) return null;

    const now = new Date();
    const start = next ? new Date(next.date) : null;
    const ongoing = next ? phaseOf(next, now) === 'ongoing' : false;

    const kicker = next && start
        ? (ongoing
            ? 'Sesja Rady · trwa teraz'
            : `Sesja Rady · ${dayWord(start, now)} ${start.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' })}`)
        : `Ostatnia sesja · ${dateLabel(latest!.session_date)}`;

    const title = next ? next.title : (latest!.headline || latest!.title);

    // Przed sesją mówimy, co jest w porządku obrad; po niej — co ustalono.
    const body = next
        ? agendaOf((next as any).details, next.description)
        : latest!.lead;

    const footer = next
        ? [duration, latest ? 'Skrót z obrad damy tu po sesji.' : null].filter(Boolean).join(' ')
        : 'Zobacz, co ustalono';

    return (
        <button
            onClick={onClick}
            className="group flex w-full items-start gap-4 rounded-2xl border border-white/10 bg-[#0d1117] p-4 text-left transition-colors hover:border-white/20 hover:bg-white/[0.04] lg:p-5"
        >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/10">
                <Landmark size={19} className="text-sky-400" aria-hidden />
            </span>

            <span className="flex min-w-0 flex-1 flex-col">
                <span className="text-[11px] font-bold uppercase tracking-widest text-sky-300">
                    {kicker}
                </span>
                <span className="mt-1 text-[15px] font-bold leading-snug text-white">
                    {title}
                </span>
                {body && (
                    <span className="mt-1.5 line-clamp-2 text-[13.5px] leading-relaxed text-neutral-400">
                        {body}
                    </span>
                )}
                {footer && (
                    <span className="mt-2 text-[12.5px] leading-relaxed text-neutral-500">
                        {footer}
                    </span>
                )}
            </span>

            <ChevronRight
                size={18}
                aria-hidden
                className="mt-1 shrink-0 text-neutral-600 transition-colors group-hover:text-neutral-300"
            />
        </button>
    );
};

export default CouncilCard;
