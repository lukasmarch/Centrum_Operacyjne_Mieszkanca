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
import { BadgeCheck, Star, Pencil, Megaphone, EyeOff, Clock, XCircle, Store } from 'lucide-react';
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
            <div className="h-32 flex items-center justify-center">
                <div className="w-6 h-6 rounded-full border-2 border-blue-500/30 border-t-blue-500 animate-spin" />
            </div>
        );
    }

    const verified = claims.filter(c => c.claim_status === 'verified');
    const pending = claims.filter(c => c.claim_status === 'pending');
    const rejected = claims.filter(c => c.claim_status === 'rejected');

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-xl font-bold mb-1">Moja firma</h2>
                <p className="text-neutral-400 text-sm">
                    Wizytówki przypisane do tego konta. Tylko Ty możesz je edytować.
                </p>
            </div>

            {claims.length === 0 && (
                <div className="bg-gradient-to-br from-blue-900/30 to-violet-900/20 rounded-2xl p-8 border border-blue-500/20 text-center">
                    <Store size={32} className="mx-auto mb-3 text-blue-400" />
                    <h3 className="font-bold text-lg mb-1">Nie masz jeszcze wizytówki</h3>
                    <p className="text-neutral-400 text-sm max-w-md mx-auto mb-5">
                        Jeśli prowadzisz firmę w gminie Rybno, jej karta prawdopodobnie już jest
                        w katalogu — tylko pusta. Przejęcie jest bezpłatne.
                    </p>
                    <button
                        onClick={onGoToCatalog}
                        className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-colors"
                    >
                        Przejmij wizytówkę firmy
                    </button>
                </div>
            )}

            {/* ── Wizytówki potwierdzone ── */}
            {verified.map(claim => (
                <div key={claim.business_id} className="bg-slate-900/50 rounded-2xl p-6 border border-gray-800/50">
                    <div className="flex items-start gap-4">
                        <div className="w-14 h-14 rounded-2xl bg-white/[0.06] border border-white/10 flex items-center justify-center overflow-hidden shrink-0">
                            {claim.profile?.logo_url
                                ? <img src={getAssetUrl(claim.profile.logo_url)} alt="" className="w-full h-full object-cover" />
                                : <span className="text-2xl">🏪</span>}
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex flex-wrap items-center gap-2 mb-1">
                                <h3 className="font-bold text-lg text-neutral-100 truncate">{claim.nazwa}</h3>
                                {claim.is_premium
                                    ? <span className="flex items-center gap-1 text-[10px] font-bold bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full">
                                        <Star size={10} /> Firma lokalna
                                      </span>
                                    : <span className="flex items-center gap-1 text-[10px] font-bold bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full">
                                        <BadgeCheck size={10} /> Zweryfikowana
                                      </span>}
                            </div>
                            <p className="text-xs text-neutral-500">
                                {claim.miasto}
                                {claim.verified_at && ` · potwierdzona ${fmtDate(claim.verified_at)}`}
                            </p>
                        </div>
                    </div>

                    {/* Dwie różne miary — pokazy to zasięg, kontakty to zainteresowanie */}
                    <div className="grid grid-cols-2 gap-3 mt-5">
                        <div className="bg-slate-950/70 rounded-xl p-3 text-center">
                            <p className="text-2xl font-bold text-white">{claim.views_count}</p>
                            <p className="text-[11px] text-neutral-500 mt-0.5">kliknięć w kontakt</p>
                        </div>
                        <div className="bg-slate-950/70 rounded-xl p-3 text-center">
                            <p className="text-2xl font-bold text-neutral-300">{claim.impressions_count ?? 0}</p>
                            <p className="text-[11px] text-neutral-500 mt-0.5">pokazów karty</p>
                        </div>
                    </div>

                    {claim.is_hidden && (
                        <p className="mt-4 text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-xl p-3 flex items-start gap-2">
                            <EyeOff size={14} className="shrink-0 mt-0.5" />
                            <span>
                                Karta jest ukryta w katalogu na wniosek o zaprzestanie przetwarzania
                                danych. Edycja działa, ale mieszkańcy jej nie widzą — napisz na
                                biuro@lumargo.pl, jeśli ma wrócić.
                            </span>
                        </p>
                    )}

                    <div className="flex flex-wrap gap-2 mt-5">
                        <button
                            onClick={() => setEditClaim(claim)}
                            className="flex items-center gap-1.5 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-xl transition-colors"
                        >
                            <Pencil size={13} /> Edytuj wizytówkę
                        </button>
                        {claim.is_premium ? (
                            <button
                                onClick={() => setAnnClaim(claim)}
                                className="flex items-center gap-1.5 px-4 py-2.5 bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-sm font-bold rounded-xl transition-colors"
                            >
                                <Megaphone size={13} /> Ogłoszenia
                            </button>
                        ) : (
                            <button
                                onClick={onGoToPricing}
                                className="flex items-center gap-1.5 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-neutral-300 text-sm font-bold rounded-xl transition-colors"
                            >
                                <Star size={13} /> Wyróżnij firmę
                            </button>
                        )}
                        <button
                            onClick={onGoToCatalog}
                            className="px-4 py-2.5 text-sm font-semibold text-neutral-400 hover:text-neutral-200 transition-colors"
                        >
                            Zobacz w katalogu →
                        </button>
                    </div>
                </div>
            ))}

            {/* ── Zgłoszenia w toku ── */}
            {pending.map(claim => (
                <div key={claim.business_id} className="bg-blue-500/5 rounded-2xl p-5 border border-blue-500/20">
                    <div className="flex items-start gap-3">
                        <Clock size={18} className="text-blue-400 shrink-0 mt-0.5" />
                        <div>
                            <h3 className="font-bold text-neutral-100">{claim.nazwa}</h3>
                            <p className="text-sm text-neutral-400 mt-1">
                                Zgłoszenie czeka na potwierdzenie — sprawdzamy je w ciągu 2 dni
                                roboczych. Odezwiemy się mailem.
                            </p>
                            <p className="text-xs text-neutral-500 mt-2">
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
                <div key={claim.business_id} className="bg-slate-900/50 rounded-2xl p-5 border border-gray-800/50">
                    <div className="flex items-start gap-3">
                        <XCircle size={18} className="text-neutral-500 shrink-0 mt-0.5" />
                        <div>
                            <h3 className="font-bold text-neutral-300">{claim.nazwa}</h3>
                            <p className="text-sm text-neutral-400 mt-1">
                                Nie potwierdziliśmy tego zgłoszenia{claim.decided_at && ` (${fmtDate(claim.decided_at)})`},
                                więc karta wróciła do puli.
                            </p>
                            <p className="text-xs text-neutral-500 mt-2">
                                Jeśli to Twoja firma, napisz na{' '}
                                <a href="mailto:biuro@lumargo.pl" className="text-blue-400 hover:text-blue-300">
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
