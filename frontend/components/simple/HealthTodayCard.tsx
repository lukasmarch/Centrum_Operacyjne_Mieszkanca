import React from 'react';
import { Stethoscope, Pill, AlertTriangle, Phone, ChevronDown } from 'lucide-react';
import type { HealthTodayResponse } from '../../types';
import { Tag } from './tv';

/**
 * „Zdrowie dziś" — kto przyjmuje w ośrodku i która apteka ma dyżur.
 *
 * Dlaczego krótko. Pełny grafik tygodnia to tabela, a strona główna odpowiada
 * na pytanie zadawane rano przy śniadaniu: „czy jest dziś mój lekarz i do
 * której". Wystarczą trzy rzeczy w wierszu — gabinet, kto, godziny.
 *
 * ⚠️ Sygnałem, który usprawiedliwia ten kafel, jest ZMIANA. Stały grafik
 * mieszkaniec zna na pamięć po dwóch wizytach; tym, czego nie zna, jest
 * „dziś lekarz nie przyjmuje" albo „dziś przyjmuje 11:00–14:30 zamiast 8:00".
 * Backend robi tu całą robotę: `_today_change_note` w `endpoints/health.py`
 * dokleja `notes` do lekarza WYŁĄCZNIE wtedy, gdy w notatce pada dzisiejsza
 * data. Obecność pola `notes` to gotowa odpowiedź na pytanie „czy dziś inaczej",
 * i tylko ona zapala bursztyn — front niczego nie parsuje.
 *
 * Kolor niesie znaczenie, tak samo jak w pasku dróg: spokojny grafik jest
 * neutralny, odstępstwo bursztynowe. Gdyby wyróżnić wszystko, wyróżnienie
 * przestaje cokolwiek znaczyć.
 *
 * Zwinięty (13.10.2026, uwaga Łukasza): cały żółty blok z sześcioma wierszami
 * grafiku był najgłośniejszą rzeczą pulpitu, a zmienia się w nim jedno zdanie.
 * Na wierzchu stoi tylko to zdanie (kto dziś nie przyjmuje); grafik i apteka
 * są pod „Rozwiń”. Zmianę ogłasza też pasek „Na żywo” — jego migawka rozwija
 * ten kafel.
 */

export interface HealthChange {
    clinic: string;
    name: string;
    /** Notatka bez daty z przodu, zdaniem zamiast wersalików */
    note: string;
    absent: boolean;
}

/** „13.10.2026 LEKARZ NIE PRZYJMUJE” → „Lekarz nie przyjmuje”. */
const cleanNote = (raw: string): string => {
    const text = raw.replace(/^\s*\d{1,2}\.\d{1,2}\.\d{2,4}\s*[:–-]?\s*/, '').trim();
    if (text && text === text.toUpperCase()) {
        const lower = text.toLowerCase();
        return lower.charAt(0).toUpperCase() + lower.slice(1);
    }
    return text;
};

/** Dzisiejsze odstępstwa od grafiku — wspólne dla kafla i paska „Na żywo”. */
export const healthChanges = (data: HealthTodayResponse | null): HealthChange[] =>
    (data?.clinics ?? []).flatMap(c =>
        c.doctors
            .filter(d => d.notes)
            .map(d => ({
                clinic: c.clinic_name,
                name: cleanName(d.name),
                note: cleanNote(d.notes as string),
                absent: /nie\s+przyjmuje/i.test(d.notes as string),
            })),
    );

/** Skrót roli — „Specjalista chorób wewnętrznych, Specjalista medycyny rodzinnej"
 *  zajmuje w kaflu tyle co reszta wiersza i nie mówi mieszkańcowi nic ponad to,
 *  co już wie z nazwy gabinetu. Pełna rola zostaje na stronie ośrodka. */
const shortRole = (role: string | null): string | null => {
    if (!role) return null;
    const first = role.split(',')[0].trim();
    return first.length > 34 ? null : first;
};

/** „Lekarz dentysta – Piotr Szumada" → „Piotr Szumada”. Nazwa gabinetu stoi
 *  obok, więc powtarzanie zawodu w nazwisku zjada wiersz. */
const cleanName = (name: string | null): string =>
    (name ?? '').replace(/^lekarz\s+\w+\s*[–-]\s*/i, '').trim();

/** Personel pomocniczy — w danych ośrodka zapisany w polu z nazwiskiem
 *  („Asystentka stomatologiczna – Dorota Zabłotna"), nie w roli. Mieszkaniec
 *  pyta, czy przyjmuje LEKARZ; asystentka pracuje w tych samych godzinach
 *  co dentysta, więc jej obecność nie wnosi nic, a zajmuje pół wiersza. */
const isSupportStaff = (name: string | null): boolean =>
    /^(asystent|higienist|rejestrator)/i.test((name ?? '').trim());

/** Wiersze kafla: godziny osobno, reszta osobno.
 *
 *  Pierwsza wersja skleiła wszystko w jedno zdanie („POZ · Joao Francisco
 *  Catenda Neto 08:00-14:00 · Mariola Zduniak-Świniarska 10:25-18:00").
 *  Na telefonie łamało się to w przypadkowych miejscach — godzina rozpadała
 *  się na „08:00-" i „14:00" w dwóch wierszach, a przecież po godzinę
 *  mieszkaniec tu przychodzi. Teraz godziny stoją w osobnej kolumnie po lewej,
 *  wyrównane do siebie i nigdy nie łamane; nazwiska zawijają się obok.
 *
 *  Jeden wiersz = jedna godzina. Dwaj dentyści pracujący 08:00–15:00 dzielą
 *  wiersz (nazwiska po przecinku), a dwoje lekarzy POZ o różnych godzinach
 *  dostaje po wierszu — bo to właśnie różnica godzin jest tu informacją.
 *
 *  Kolejność chronologiczna, nie alfabetyczna: kafel czyta się jak grafik dnia.
 */
interface Row {
    hours: string;
    clinic: string;
    who: string;
}

const buildRows = (
    clinics: { clinic_name: string; doctors: { name: string | null; role: string | null; hours: string }[] }[],
): Row[] => {
    const rows: Row[] = [];
    for (const clinic of clinics) {
        // Asystentkę pomijamy tylko wtedy, gdy zostaje ktoś jeszcze — inaczej
        // gabinet zniknąłby z listy w dniu, w którym pracuje sam personel pomocniczy
        const medics = clinic.doctors.filter(d => !isSupportStaff(d.name));
        const shown = medics.length ? medics : clinic.doctors;

        const byHours = new Map<string, string[]>();
        for (const doc of shown) {
            const label = cleanName(doc.name) || shortRole(doc.role) || '';
            const list = byHours.get(doc.hours) ?? [];
            if (label) list.push(label);
            byHours.set(doc.hours, list);
        }
        for (const [hours, names] of byHours) {
            rows.push({ clinic: clinic.clinic_name, hours, who: names.join(', ') });
        }
    }
    return rows.sort((a, b) => a.hours.localeCompare(b.hours));
};

/** „08:00-16:00" → „08:00–16:00". Półpauza czyta się w tabeli lepiej niż łącznik,
 *  a backend skleja godziny zwykłym minusem. */
const prettyHours = (hours: string): string => hours.replace(/\s*-\s*/, '–');

interface HealthTodayCardProps {
    data: HealthTodayResponse | null;
    open: boolean;
    onToggle: () => void;
}

const HealthTodayCard: React.FC<HealthTodayCardProps> = ({ data, open, onToggle }) => {
    // Cisza zamiast szkieletu: kafel wchodzi między gotowe karty „Na dziś",
    // a migający placeholder przy każdym wejściu jest gorszy niż treść
    // pojawiająca się o sekundę później (ta sama zasada co w pasku dróg)
    if (!data) return null;

    const clinics = data.clinics ?? [];
    const pharmacy = (data.pharmacies ?? [])[0];
    if (!clinics.length && !pharmacy) return null;

    const rows = buildRows(clinics);
    const changes = healthChanges(data);
    const absentNames = new Set(changes.filter(c => c.absent).map(c => c.name));
    const hasChange = changes.length > 0;

    // Zdanie na wierzchu: zmiana, a bez niej — kiedy ośrodek dziś pracuje
    const first = rows[0]?.hours.split('-')[0]?.trim();
    const last = rows.map(r => r.hours.split('-')[1]?.trim()).filter(Boolean).sort().pop();
    const summary = rows.length
        ? `przyjmuje dziś${first && last ? ` ${first}–${last}` : ''}`
        : 'dziś nie przyjmuje';

    return (
        <section id="osrodek-zdrowia" aria-label="Ośrodek zdrowia" className="scroll-mt-24">
            <Tag as="h2">Ośrodek zdrowia</Tag>
            <div className="bg-tv-panel">
            <button
                onClick={onToggle}
                aria-expanded={open}
                aria-controls="osrodek-zdrowia-grafik"
                className="flex min-h-[52px] w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-tv-panel2"
            >
                <Stethoscope size={20} className="shrink-0 text-tv-muted" aria-hidden />
                <span className="min-w-0 flex-1 text-[15px] leading-snug">
                    {hasChange ? (
                        changes.map((c, i) => (
                            <span key={i} className="flex flex-wrap items-baseline gap-x-2">
                                <span className="font-cond bg-tv-yellow px-1.5 py-0.5 text-[13px] font-extrabold uppercase leading-none tracking-wide text-tv-ink">
                                    {c.absent ? 'Dziś nie przyjmuje' : 'Zmiana dziś'}
                                </span>
                                <span className="font-semibold text-white">
                                    {c.name || c.clinic}
                                    <span className="font-normal text-tv-muted"> · {c.clinic}{!c.absent && ` — ${c.note}`}</span>
                                </span>
                            </span>
                        ))
                    ) : (
                        <span className="text-tv-paper">{summary.charAt(0).toUpperCase() + summary.slice(1)}</span>
                    )}
                </span>
                <span className="flex shrink-0 items-center gap-1 text-[14px] font-bold text-tv-bluesoft">
                    <span>{open ? 'Zwiń' : 'Rozwiń'}</span>
                    <ChevronDown size={18} aria-hidden className={`transition-transform ${open ? 'rotate-180' : ''}`} />
                </span>
            </button>

            {open && (
                <div id="osrodek-zdrowia-grafik" className="border-t border-tv-seam px-4 pb-3 pt-2.5 sm:pl-[52px]">
                    {rows.length > 0 ? (
                        <ul className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                            {rows.map((row, i) => {
                                const off = row.who.split(', ').some(n => absentNames.has(n));
                                return (
                                    <React.Fragment key={i}>
                                        <li className={`whitespace-nowrap text-[15px] font-semibold tabular-nums ${off ? 'text-tv-muted line-through' : 'text-white'}`}>
                                            {prettyHours(row.hours)}
                                        </li>
                                        <li className="min-w-0 text-[15px] leading-snug text-tv-muted">
                                            <span className="font-semibold text-tv-paper">{row.clinic}</span>
                                            {row.who && <> · <span className={off ? 'line-through' : ''}>{row.who}</span></>}
                                            {off && (
                                                <span className="ml-2 inline-flex items-center gap-1 font-semibold text-tv-yellow">
                                                    <AlertTriangle size={14} aria-hidden />
                                                    nie przyjmuje
                                                </span>
                                            )}
                                        </li>
                                    </React.Fragment>
                                );
                            })}
                        </ul>
                    ) : (
                        <p className="text-[15px] text-tv-muted">Dziś ośrodek nie przyjmuje.</p>
                    )}

                    {pharmacy && (
                        <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-0.5 border-t border-tv-seam pt-2 text-[15px] text-tv-muted">
                            <Pill size={15} className="shrink-0" aria-hidden />
                            <span>Apteka dyżurna:</span>
                            <span className="font-semibold text-white">{pharmacy.name}</span>
                            <span className="whitespace-nowrap tabular-nums">{prettyHours(pharmacy.hours)}</span>
                            {pharmacy.phone && (
                                <a
                                    href={`tel:${pharmacy.phone.replace(/[^\d+]/g, '')}`}
                                    className="inline-flex min-h-[44px] items-center gap-1 font-semibold text-tv-bluesoft underline underline-offset-2 hover:text-white"
                                >
                                    <Phone size={12} aria-hidden />
                                    {pharmacy.phone}
                                </a>
                            )}
                        </p>
                    )}
                </div>
            )}
            </div>
        </section>
    );
};

export default HealthTodayCard;
