import React, { useEffect, useState } from 'react';
import { ClipboardList, MapPin, ArrowRight, Camera } from 'lucide-react';
import { fetchReports, getImageUrl, STATUS_CONFIG } from '../../src/services/reportsApi';
import { Report } from '../../types';

interface ReportsMiniProps {
    onOpenReports: () => void;
}

/**
 * „Zgłoszenia 24" na stronie głównej — miejsce MIESZKAŃCA.
 *
 * Decyzja Łukasza z 12.08.2026: nie budujemy osobnych ogłoszeń mieszkańców,
 * bo zabiłyby tę sekcję. Mieszkaniec ma jedno miejsce, w którym coś od siebie
 * wnosi, i to ono ma go wiązać z portalem — dwa konkurencyjne formularze na
 * jedną gminę oznaczają dwa na wpół żywe.
 *
 * Publikowane są WYŁĄCZNIE zgłoszenia po moderacji: backend trzyma nowe wpisy
 * w statusie `pending`, a `HIDDEN_STATUSES` nie wypuszcza ani ich, ani
 * odrzuconych. Ten kafel nie robi więc żadnej własnej bramki — pokazuje to,
 * co administrator przepuścił.
 *
 * Maksymalnie DWA wpisy: sekcja ma zapraszać, a nie odbierać miejsce feedowi.
 */
const MAX_REPORTS = 2;

/**
 * Po ilu dniach ZAŁATWIONE zgłoszenie schodzi ze strony głównej.
 *
 * 24.09.2026 kafel pokazywał dwa jedyne zgłoszenia, oba `resolved`:
 * „Brak body — awaria sieci wodociągowej" (sprzed 22 dni) i „Brak Wody"
 * (sprzed 33). Statusu nie było widać wcale, więc mieszkaniec czytał to jako
 * TRWAJĄCĄ awarię wodociągu — przy tym akurat temacie najgorzej, jak można.
 *
 * Sprawa zamknięta jest dowodem, że zgłaszanie ma sens, i dlatego zostaje —
 * ale tylko póki jest świeża. Ta sama zasada, co wygasanie alertu w feedzie.
 *
 * Miesiąc, nie dwa tygodnie (decyzja Łukasza 24.09): przy dwóch zgłoszeniach
 * na gminę krótszy próg opróżniłby kafel całkiem, a strona główna straciłaby
 * jedyny dowód, że ktoś z tej sekcji korzystał. Załatwiona sprawa z plakietką
 * „Rozwiązane" mówi więcej niż zaproszenie do pustego miejsca.
 */
const RESOLVED_MAX_AGE_DAYS = 30;

/** Sprawy zamknięte, których nie warto już pokazywać na stronie głównej. */
const isStaleResolved = (report: Report): boolean => {
    if (report.status !== 'resolved') return false;
    const stamp = report.resolved_at || report.updated_at || report.created_at;
    const days = (Date.now() - new Date(stamp).getTime()) / 86_400_000;
    return days > RESOLVED_MAX_AGE_DAYS;
};

const ReportsMini: React.FC<ReportsMiniProps> = ({ onOpenReports }) => {
    const [reports, setReports] = useState<Report[] | null>(null);

    useEffect(() => {
        let cancelled = false;
        // Z zapasem: część wpisów odpadnie na starzeniu, a kafel ma pokazać
        // tyle świeżych, ile naprawdę jest — nie tyle, ile zostało z pierwszych dwóch.
        fetchReports({ limit: MAX_REPORTS * 4, sort: 'newest' })
            .then(res => {
                if (cancelled) return;
                const swieze = (res.reports ?? []).filter(r => !isStaleResolved(r));
                setReports(swieze.slice(0, MAX_REPORTS));
            })
            .catch(() => { if (!cancelled) setReports([]); });
        return () => { cancelled = true; };
    }, []);

    if (reports === null) return null;

    const timeAgo = (iso: string) => {
        const hours = Math.floor((Date.now() - new Date(iso).getTime()) / 3_600_000);
        if (hours < 1) return 'przed chwilą';
        if (hours < 24) return `${hours}h temu`;
        return `${Math.floor(hours / 24)}d temu`;
    };

    return (
        <section aria-label="Zgłoszenia 24">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-neutral-500">
                <ClipboardList size={13} className="text-cyan-400" aria-hidden />
                Zgłoszenia 24
                <span className="font-medium normal-case tracking-normal text-neutral-600">
                    · zgłoszone przez mieszkańców
                </span>
            </h2>

            {/*
              Pusto znaczy „bądź pierwszy", nie „tu nic nie ma". To jedyna sekcja,
              w której mieszkaniec CZEGOŚ DODAJE, więc zaproszenie musi stać nawet
              wtedy — a zwłaszcza wtedy — gdy lista jest pusta
            */}
            {reports.length === 0 ? (
                <button
                    onClick={onOpenReports}
                    className="group flex w-full items-center gap-4 rounded-2xl border border-dashed border-cyan-500/25 bg-cyan-500/[0.04] p-5 text-left transition-colors hover:border-cyan-500/40"
                >
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-cyan-500/10">
                        <Camera size={20} className="text-cyan-400" aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                        <span className="block text-base font-semibold text-white">
                            Zepsuta lampa? Dziura w drodze?
                        </span>
                        <span className="mt-0.5 block text-sm text-neutral-400">
                            Zrób zdjęcie i zgłoś. Sprawdzamy i publikujemy jak najszybciej.
                        </span>
                    </span>
                    <ArrowRight
                        size={18}
                        aria-hidden
                        className="shrink-0 text-neutral-600 transition-colors group-hover:text-cyan-300"
                    />
                </button>
            ) : (
                <>
                    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 lg:gap-4">
                        {reports.map(report => (
                            <button
                                key={report.id}
                                onClick={onOpenReports}
                                className="flex items-start gap-3 rounded-2xl border border-white/10 bg-[#0d1117] p-4 text-left transition-colors hover:border-white/20"
                            >
                                <span className="h-14 w-14 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-cyan-500/10">
                                    {report.image_url ? (
                                        <img
                                            src={getImageUrl(report.image_url)}
                                            alt=""
                                            loading="lazy"
                                            className="h-full w-full object-cover"
                                        />
                                    ) : (
                                        <span className="flex h-full w-full items-center justify-center">
                                            <ClipboardList size={20} className="text-cyan-400/60" aria-hidden />
                                        </span>
                                    )}
                                </span>
                                <span className="min-w-0 flex-1">
                                    {/*
                                      Status PRZY wieku, nie zamiast niego: „22d temu"
                                      bez słowa „Rozwiązane" czyta się jak trwająca
                                      awaria — a to właśnie zgłaszają mieszkańcy
                                      (brak wody, brak prądu)
                                    */}
                                    <span className="flex flex-wrap items-center gap-1.5 text-[11px] font-medium text-neutral-500">
                                        {timeAgo(report.created_at)}
                                        {STATUS_CONFIG[report.status] && (
                                            <span
                                                className="rounded-full px-1.5 py-px text-[10px] font-semibold"
                                                style={{
                                                    color: STATUS_CONFIG[report.status].color,
                                                    backgroundColor: `${STATUS_CONFIG[report.status].color}1f`,
                                                }}
                                            >
                                                {STATUS_CONFIG[report.status].label}
                                            </span>
                                        )}
                                    </span>
                                    {/* Bez `block` — kasuje `line-clamp` (patrz NewsMini) */}
                                    <span className="mt-0.5 line-clamp-2 text-base font-medium leading-snug text-neutral-100">
                                        {report.title}
                                    </span>
                                    {report.location_name && (
                                        <span className="mt-1 flex items-center gap-1 text-[13px] text-neutral-500">
                                            <MapPin size={11} aria-hidden />{report.location_name}
                                        </span>
                                    )}
                                </span>
                            </button>
                        ))}
                    </div>
                    <button
                        onClick={onOpenReports}
                        className="mt-3 flex min-h-[44px] items-center gap-1.5 text-sm font-semibold text-cyan-400 transition-colors hover:text-cyan-300"
                    >
                        Zgłoś usterkę albo zobacz mapę
                        <ArrowRight size={15} aria-hidden />
                    </button>
                </>
            )}
        </section>
    );
};

export default ReportsMini;
