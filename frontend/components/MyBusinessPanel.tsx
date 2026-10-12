/**
 * „Moja firma" — wizytówki przypisane do zalogowanego konta.
 *
 * Powód istnienia (19.08.2026). Wizytówka od początku była podpisana do
 * użytkownika w bazie (`business_profiles.user_id`), ale w interfejsie nie
 * widniało to NIGDZIE. Właściciel, który zakładał konto wyłącznie po to, żeby
 * przejąć kartę firmy, po zalogowaniu widział profil, który o jego firmie nie
 * wiedział; dostęp do edycji istniał tylko przez kafelek w katalogu — a katalog
 * pokazuje 60 pozycji i pomija karty ukryte na wniosek firmy.
 *
 * Panel pokazuje WSZYSTKIE trzy stany, z odmową włącznie. Odrzucenie kasuje
 * profil w bazie, więc bez pozycji z `business_claim_log` zgłoszenie po prostu
 * znikało z ekranu i wyglądało jak awaria serwisu.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { BadgeCheck, Star, Pencil, Megaphone, EyeOff, Clock, XCircle, Store, ChevronRight } from 'lucide-react';
import { Tag, Skeleton } from './simple/tv';
import { fetchMyClaims, getAssetUrl, MyClaim } from '../src/services/businessApi';
import { EditProfileModal, AnnouncementsModal } from './BusinessOwnerModals';

const fmtDate = (iso?: string | null): string => {
    if (!iso) return '';
    try {
        return new Date(iso).toLocaleDateString('pl-PL', {
            day: 'numeric', month: 'long', year: 'numeric',
        });
    } catch {
        return '';
    }
};

const MyBusinessPanel: React.FC<{
    onGoToCatalog: () => void;
    onGoToPricing: () => void;
}> = ({ onGoToCatalog, onGoToPricing }) => {
    const [claims, setClaims] = useState<MyClaim[] | null>(null);
    const [editClaim, setEditClaim] = useState<MyClaim | null>(null);
    const [annClaim, setAnnClaim] = useState<MyClaim | null>(null);

    const load = useCallback(() => {
        fetchMyClaims().then(setClaims).catch(() => setClaims([]));
    }, []);

    useEffect(() => { load(); }, [load]);

    if (claims === null) {
        return (
            <div className="space-y-3" aria-busy="true">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-32" />
            </div>
        );
    }

    const verified = claims.filter(c => c.claim_status === 'verified');
    const pending = claims.filter(c => c.claim_status === 'pending');
    const rejected = claims.filter(c => c.claim_status === 'rejected');

    return (
        <div className="space-y-6">
            <div>
                <h2 className="font-cond text-[24px] font-extrabold leading-tight text-white">Moja firma</h2>
                <p className="mt-0.5 text-[15px] text-tv-muted">
                    Wizytówki przypisane do tego konta. Tylko Ty możesz je edytować.
                </p>
            </div>

            {claims.length === 0 && (
                <div className="border-t-2 border-tv-blue bg-tv-panel p-4 lg:p-5">
                    <div className="flex items-start gap-3">
                        <Store size={22} className="mt-1 shrink-0 text-tv-muted" aria-hidden />
                        <div>
                            <h3 className="font-cond text-[21px] font-extrabold leading-snug text-white">Nie masz jeszcze wizytówki</h3>
                            <p className="mt-1 max-w-[60ch] text-[15px] leading-relaxed text-[#d7dbe8]">
                                Jeśli prowadzisz firmę w gminie Rybno, jej karta prawdopodobnie już jest
                                w katalogu — tylko pusta. Przejęcie jest bezpłatne.
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onGoToCatalog}
                        className="font-cond mt-4 inline-flex min-h-[52px] items-center bg-tv-blue px-5 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff]"
                    >
                        Przejmij wizytówkę firmy
                    </button>
                </div>
            )}

            {/* ── Wizytówki potwierdzone ── */}
            {verified.map(claim => (
                <div key={claim.business_id} className="border-t-2 border-tv-blue bg-tv-panel p-4 lg:p-5">
                    <div className="flex items-start gap-3">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden bg-tv-panel2">
                            {claim.profile?.logo_url
                                ? <img src={getAssetUrl(claim.profile.logo_url)} alt="" className="h-full w-full object-cover" />
                                : <Store size={20} className="text-tv-muted" aria-hidden />}
                        </div>
                        <div className="min-w-0 flex-1">
                            <div className="mb-1 flex flex-wrap items-center gap-2">
                                <h3 className="truncate text-[18px] font-bold text-white">{claim.nazwa}</h3>
                                {claim.is_premium
                                    ? <Tag tone="paper"><span className="inline-flex items-center gap-1"><Star size={12} aria-hidden /> Firma lokalna</span></Tag>
                                    : <Tag tone="seam"><span className="inline-flex items-center gap-1"><BadgeCheck size={12} aria-hidden /> Zweryfikowana</span></Tag>}
                            </div>
                            <p className="text-[13px] text-tv-muted">
                                {claim.miasto}
                                {claim.verified_at && ` · potwierdzona ${fmtDate(claim.verified_at)}`}
                            </p>
                        </div>
                    </div>

                    {/* Dwie różne miary — pokazy to zasięg, kontakty to zainteresowanie */}
                    <div className="mt-4 grid grid-cols-2 gap-px bg-tv-seam">
                        <div className="bg-tv-panel2 px-3.5 py-3">
                            <p className="font-cond tabular text-[26px] font-extrabold leading-none text-white">{claim.views_count}</p>
                            <p className="mt-1 text-[13px] text-tv-muted">kliknięć w kontakt</p>
                        </div>
                        <div className="bg-tv-panel2 px-3.5 py-3">
                            <p className="font-cond tabular text-[26px] font-extrabold leading-none text-tv-paper">{claim.impressions_count ?? 0}</p>
                            <p className="mt-1 text-[13px] text-tv-muted">pokazów karty</p>
                        </div>
                    </div>

                    {claim.is_hidden && (
                        <p className="mt-4 flex items-start gap-2 bg-tv-yellow px-3 py-2.5 text-[14px] leading-snug text-tv-ink">
                            <EyeOff size={16} className="mt-0.5 shrink-0" aria-hidden />
                            <span>
                                Karta jest ukryta w katalogu na wniosek o zaprzestanie przetwarzania
                                danych. Edycja działa, ale mieszkańcy jej nie widzą — napisz na
                                biuro@lumargo.pl, jeśli ma wrócić.
                            </span>
                        </p>
                    )}

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                        <button
                            onClick={() => setEditClaim(claim)}
                            className="font-cond inline-flex min-h-[44px] items-center gap-1.5 bg-tv-blue px-4 text-[16px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff]"
                        >
                            <Pencil size={15} aria-hidden /> Edytuj wizytówkę
                        </button>
                        {claim.is_premium ? (
                            <button
                                onClick={() => setAnnClaim(claim)}
                                className="font-cond inline-flex min-h-[44px] items-center gap-1.5 bg-tv-paper px-4 text-[16px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-white"
                            >
                                <Megaphone size={15} aria-hidden /> Ogłoszenia
                            </button>
                        ) : (
                            <button
                                onClick={onGoToPricing}
                                className="font-cond inline-flex min-h-[44px] items-center gap-1.5 bg-tv-paper px-4 text-[16px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-white"
                            >
                                <Star size={15} aria-hidden /> Wyróżnij firmę
                            </button>
                        )}
                        <button
                            onClick={onGoToCatalog}
                            className="inline-flex min-h-[44px] items-center gap-1 px-2 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline"
                        >
                            Zobacz w katalogu <ChevronRight size={16} aria-hidden />
                        </button>
                    </div>
                </div>
            ))}

            {/* ── Zgłoszenia w toku ── */}
            {pending.map(claim => (
                <div key={claim.business_id} className="bg-tv-panel p-4">
                    <div className="flex items-start gap-3">
                        <Clock size={18} className="mt-0.5 shrink-0 text-tv-muted" aria-hidden />
                        <div>
                            <h3 className="text-[16px] font-bold text-white">{claim.nazwa}</h3>
                            <p className="mt-1 text-[15px] leading-relaxed text-[#d7dbe8]">
                                Zgłoszenie czeka na potwierdzenie — sprawdzamy je w ciągu 2 dni
                                roboczych. Odezwiemy się mailem.
                            </p>
                            <p className="mt-2 text-[13px] text-tv-muted">
                                {claim.source === 'manual'
                                    ? 'Firma dopisana ręcznie — do czasu potwierdzenia nie jest widoczna w katalogu.'
                                    : 'Dane firmy pochodzą z CEIDG — potwierdzamy tylko, że karta należy do Ciebie.'}
                                {claim.created_at && ` Zgłoszone ${fmtDate(claim.created_at)}.`}
                            </p>
                        </div>
                    </div>
                </div>
            ))}

            {/* ── Odmowy ── */}
            {rejected.map(claim => (
                <div key={claim.business_id} className="bg-tv-panel p-4">
                    <div className="flex items-start gap-3">
                        <XCircle size={18} className="mt-0.5 shrink-0 text-tv-muted" aria-hidden />
                        <div>
                            <h3 className="text-[16px] font-bold text-tv-paper">{claim.nazwa}</h3>
                            <p className="mt-1 text-[15px] leading-relaxed text-[#d7dbe8]">
                                Nie potwierdziliśmy tego zgłoszenia{claim.decided_at && ` (${fmtDate(claim.decided_at)})`},
                                więc karta wróciła do puli.
                            </p>
                            <p className="mt-2 text-[13px] text-tv-muted">
                                Jeśli to Twoja firma, napisz na{' '}
                                <a href="mailto:biuro@lumargo.pl" className="font-semibold text-tv-bluesoft underline underline-offset-2 hover:text-white">
                                    biuro@lumargo.pl
                                </a>{' '}
                                — wystarczy cokolwiek, co wiąże Cię z firmą. Załatwimy to bez
                                czekania na kolejny wniosek.
                            </p>
                        </div>
                    </div>
                </div>
            ))}

            {editClaim && (
                <EditProfileModal
                    claim={editClaim}
                    onClose={() => setEditClaim(null)}
                    onSaved={load}
                />
            )}
            {annClaim && (
                <AnnouncementsModal
                    claim={annClaim}
                    onClose={() => setAnnClaim(null)}
                    onChanged={load}
                />
            )}
        </div>
    );
};

export default MyBusinessPanel;
