import React from 'react';
import { Stethoscope, Pill, AlertTriangle, Phone } from 'lucide-react';
import { useHealthToday } from '../../src/hooks/useHealthToday';

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
 */

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

const HealthTodayCard: React.FC<{ onOpenAssistant?: () => void }> = () => {
    const { data, loading, error } = useHealthToday();

    // Cisza zamiast szkieletu: kafel wchodzi między gotowe karty „Na dziś",
    // a migający placeholder przy każdym wejściu jest gorszy niż treść
    // pojawiająca się o sekundę później (ta sama zasada co w pasku dróg)
    if (loading || error || !data) return null;

    const clinics = data.clinics ?? [];
    const pharmacy = (data.pharmacies ?? [])[0];
    if (!clinics.length && !pharmacy) return null;

    const rows = buildRows(clinics);
    const changes = clinics.flatMap(c =>
        c.doctors.filter(d => d.notes).map(d => ({ clinic: c.clinic_name, doctor: d })),
    );
    const hasChange = changes.length > 0;

    return (
        <div
            className={`px-4 py-3 ${hasChange ? 'bg-tv-yellow text-tv-ink' : 'bg-tv-panel'}`}
        >
            <div className="flex items-start gap-3">
                <Stethoscope
                    size={20}
                    className={`mt-0.5 shrink-0 ${hasChange ? 'text-tv-ink' : 'text-tv-muted'}`}
                    aria-hidden
                />

                <div className="min-w-0 flex-1">
                    <p className={`text-[15px] font-bold leading-snug ${hasChange ? "text-tv-ink" : "text-tv-paper"}`}>
                        Ośrodek zdrowia dziś
                    </p>

                    {rows.length > 0 ? (
                        <ul className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                            {rows.map((row, i) => (
                                <React.Fragment key={i}>
                                    <li className={`whitespace-nowrap text-[15px] font-semibold tabular-nums ${hasChange ? "text-tv-ink" : "text-white"}`}>
                                        {prettyHours(row.hours)}
                                    </li>
                                    <li className={`min-w-0 text-[15px] leading-snug ${hasChange ? "text-tv-ink" : "text-tv-muted"}`}>
                                        <span className={`font-semibold ${hasChange ? "text-tv-ink" : "text-tv-paper"}`}>{row.clinic}</span>
                                        {row.who && <> · {row.who}</>}
                                    </li>
                                </React.Fragment>
                            ))}
                        </ul>
                    ) : (
                        <p className={`mt-1 text-[15px] ${hasChange ? "text-tv-ink" : "text-tv-muted"}`}>
                            Dziś ośrodek nie przyjmuje.
                        </p>
                    )}

                    {/* Zmiana jest jedynym powodem, dla którego ktoś ma przeczytać
                        ten kafel uważnie — dostaje własny wiersz, nie przypis */}
                    {hasChange && (
                        <div className="mt-2 space-y-1 border-t border-black/25 pt-2">
                            {changes.map(({ clinic, doctor }, i) => (
                                <p key={i} className="flex items-start gap-2 text-[15px] font-semibold leading-snug text-tv-ink">
                                    <AlertTriangle size={15} className="mt-0.5 shrink-0" aria-hidden />
                                    <span>
                                        <span className="font-semibold">
                                            {clinic}
                                            {cleanName(doctor.name) && ` · ${cleanName(doctor.name)}`}
                                        </span>
                                        {' — '}
                                        {doctor.notes}
                                    </span>
                                </p>
                            ))}
                        </div>
                    )}

                    {pharmacy && (
                        <p className={`mt-2 flex flex-wrap items-center gap-x-2 gap-y-0.5 border-t pt-2 text-[15px] ${hasChange ? 'border-black/25 text-tv-ink' : 'border-tv-seam text-tv-muted'}`}>
                            <Pill size={15} className="shrink-0" aria-hidden />
                            <span>Apteka dyżurna:</span>
                            <span className={`font-semibold ${hasChange ? 'text-tv-ink' : 'text-white'}`}>{pharmacy.name}</span>
                            <span className="whitespace-nowrap tabular-nums">{prettyHours(pharmacy.hours)}</span>
                            {pharmacy.phone && (
                                <a
                                    href={`tel:${pharmacy.phone.replace(/[^\d+]/g, '')}`}
                                    className={`inline-flex min-h-[44px] items-center gap-1 font-semibold underline underline-offset-2 ${hasChange ? "text-tv-ink" : "text-tv-bluesoft hover:text-white"}`}
                                >
                                    <Phone size={12} aria-hidden />
                                    {pharmacy.phone}
                                </a>
                            )}
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
};

export default HealthTodayCard;
