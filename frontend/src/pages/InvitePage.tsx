/**
 * Zaproszenie dla sołtysa — `/zaproszenie?kod=…`.
 *
 * Link wręcza Łukasz po rozmowie telefonicznej. Strona najpierw mówi, CZYM
 * zostanie przyjmujący („Sołtys sołectwa Żabiny"), potem daje dwie drogi:
 * nowe konto (rejestracja z kodem — rola od razu) albo logowanie na istniejące
 * i jedno kliknięcie „Przyjmij". Rejestracja jest ta sama co dla mieszkańców.
 */
import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import RegisterPage from './RegisterPage';
import LoginPage from './LoginPage';
import { Notice, PageHead, Skeleton } from '../../components/simple/tv';
import { InvitationPublic, acceptInvitation, fetchInvitation } from '../services/solectwaApi';

interface Props {
    onDone: () => void;
    onNavigate: (page: 'terms' | 'privacy' | 'dashboard') => void;
}

const inviteFromUrl = () => new URLSearchParams(window.location.search).get('kod') ?? '';

const InvitePage: React.FC<Props> = ({ onDone, onNavigate }) => {
    const { isAuthenticated, user } = useAuth();
    const [token] = useState(inviteFromUrl);
    const [invitation, setInvitation] = useState<InvitationPublic | null>(null);
    const [error, setError] = useState('');
    const [mode, setMode] = useState<'register' | 'login'>('register');
    const [accepting, setAccepting] = useState(false);

    useEffect(() => {
        if (!token) {
            setError('W linku brakuje kodu zaproszenia.');
            return;
        }
        fetchInvitation(token).then(setInvitation).catch((e) => setError(e.message));
    }, [token]);

    const accept = async () => {
        setAccepting(true);
        setError('');
        try {
            await acceptInvitation(token);
            onDone();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Nie udało się przyjąć zaproszenia');
            setAccepting(false);
        }
    };

    // Po zalogowaniu/rejestracji ekrany logowania wołają onNavigate('dashboard').
    // Tu to przechwytujemy: po logowaniu zostajemy na zaproszeniu (przycisk
    // „Przyjmij"), po rejestracji z kodem rola już jest — idziemy do panelu.
    const afterAuth = (page: string) => {
        if (page === 'terms' || page === 'privacy') onNavigate(page);
        else if (page === 'register') setMode('register');
        else if (page === 'login') setMode('login');
    };

    // Główka bez kickera „Zaproszenie” nad tytułem — słowo weszło do tytułu
    const header = (
        <div className="mx-auto mb-5 max-w-md">
            {invitation ? (
                <PageHead
                    title={<>Zaproszenie: {invitation.signed_as}</>}
                    sub={<>Po przyjęciu zaproszenia będziesz publikować ogłoszenia sołectwa — wystarczy
                        zdjęcie pisma. Konto ma plan Premium bez opłat na czas pełnienia funkcji.</>}
                />
            ) : !error && (
                <div aria-busy="true" className="space-y-2">
                    <Skeleton className="h-9 w-3/4" />
                    <Skeleton className="h-5 w-full" />
                    <span className="sr-only">Wczytuję zaproszenie…</span>
                </div>
            )}
        </div>
    );

    if (error && !invitation) {
        return (
            <div className="mx-auto max-w-md space-y-4 py-16">
                <PageHead title="Nie można otworzyć zaproszenia" />
                <Notice tone="warn" role="alert">{error}</Notice>
            </div>
        );
    }
    if (!invitation) return <div className="py-16">{header}</div>;

    if (invitation.state !== 'active') {
        return (
            <div className="py-16">
                {header}
                <div className="mx-auto max-w-md">
                    <Notice tone="warn">{invitation.message}</Notice>
                </div>
            </div>
        );
    }

    if (isAuthenticated && user) {
        return (
            <div className="py-16">
                {header}
                <div className="mx-auto max-w-md border-t-2 border-tv-blue bg-tv-panel p-5 sm:p-6">
                    <p className="text-[15px] text-tv-muted">Jesteś zalogowany jako</p>
                    <p className="mt-1 break-words text-[16px] font-semibold text-white">{user.full_name} · {user.email}</p>
                    {error && <div className="mt-4"><Notice tone="warn" role="alert">{error}</Notice></div>}
                    <button onClick={accept} disabled={accepting}
                        className="font-cond mt-5 inline-flex min-h-[52px] w-full items-center justify-center bg-tv-blue px-4 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-not-allowed disabled:opacity-50">
                        {accepting ? 'Przyjmuję…' : 'Przyjmij zaproszenie'}
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="py-8">
            {header}
            {/* Dwie drogi jako przełącznik: aktywna = papier, jak pozycja nawigacji */}
            <div role="group" aria-label="Konto" className="mx-auto flex max-w-md gap-px bg-tv-seam">
                {(['register', 'login'] as const).map((m) => (
                    <button key={m} onClick={() => setMode(m)} aria-pressed={mode === m}
                        className={`font-cond min-h-[44px] flex-1 px-3 text-[15px] font-bold uppercase tracking-wide transition-colors ${
                            mode === m ? 'bg-tv-paper text-tv-ink' : 'bg-tv-panel text-tv-paper hover:bg-tv-panel2 hover:text-white'
                        }`}>
                        {m === 'register' ? 'Nowe konto' : 'Mam już konto'}
                    </button>
                ))}
            </div>
            {mode === 'register'
                ? <RegisterPage onNavigate={afterAuth} inviteToken={token} onRegistered={onDone} />
                : <LoginPage onNavigate={afterAuth} />}
        </div>
    );
};

export default InvitePage;
