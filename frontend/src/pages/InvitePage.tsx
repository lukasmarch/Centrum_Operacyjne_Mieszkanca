/**
 * Zaproszenie dla sołtysa — `/zaproszenie?kod=…`.
 *
 * Link wręcza Łukasz po rozmowie telefonicznej. Strona najpierw mówi, CZYM
 * zostanie przyjmujący („Sołtys sołectwa Żabiny"), potem daje dwie drogi:
 * nowe konto (rejestracja z kodem — rola od razu) albo logowanie na istniejące
 * i jedno kliknięcie „Przyjmij". Rejestracja jest ta sama co dla mieszkańców.
 */
import React, { useEffect, useState } from 'react';
import { BadgeCheck, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import RegisterPage from './RegisterPage';
import LoginPage from './LoginPage';
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

    const header = (
        <div className="max-w-md mx-auto text-center mb-6 px-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Zaproszenie</p>
            {invitation ? (
                <>
                    <h1 className="text-2xl font-black mt-2 text-white flex items-center justify-center gap-2">
                        <BadgeCheck className="w-6 h-6 text-emerald-400" /> {invitation.signed_as}
                    </h1>
                    <p className="text-neutral-400 text-sm mt-3 leading-relaxed">
                        Po przyjęciu zaproszenia będziesz publikować ogłoszenia sołectwa — wystarczy
                        zdjęcie pisma. Konto ma plan Premium bez opłat na czas pełnienia funkcji.
                    </p>
                </>
            ) : !error && <Loader2 className="w-6 h-6 animate-spin text-neutral-500 mx-auto mt-4" />}
        </div>
    );

    if (error && !invitation) {
        return (
            <div className="min-h-[60vh] flex items-center justify-center px-4">
                <div className="max-w-md text-center">
                    <h1 className="text-xl font-bold mb-2">Nie można otworzyć zaproszenia</h1>
                    <p className="text-neutral-400">{error}</p>
                </div>
            </div>
        );
    }
    if (!invitation) return <div className="py-16">{header}</div>;

    if (invitation.state !== 'active') {
        return (
            <div className="py-16">
                {header}
                <p className="max-w-md mx-auto text-center text-amber-300 px-4">{invitation.message}</p>
            </div>
        );
    }

    if (isAuthenticated && user) {
        return (
            <div className="py-16 px-4">
                {header}
                <div className="max-w-md mx-auto bg-gray-950 rounded-3xl p-8 border border-gray-800/50 text-center">
                    <p className="text-sm text-neutral-400">Jesteś zalogowany jako</p>
                    <p className="font-semibold mt-1">{user.full_name} · {user.email}</p>
                    {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
                    <button onClick={accept} disabled={accepting}
                        className="mt-6 w-full rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3 font-semibold text-white inline-flex items-center justify-center gap-2">
                        {accepting && <Loader2 className="w-4 h-4 animate-spin" />}
                        Przyjmij zaproszenie
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="py-8">
            {header}
            <div className="max-w-md mx-auto flex rounded-xl bg-gray-950 border border-gray-800/50 p-1 mb-2 mx-4 sm:mx-auto">
                {(['register', 'login'] as const).map((m) => (
                    <button key={m} onClick={() => setMode(m)}
                        className={`flex-1 rounded-lg py-2 text-sm font-semibold ${mode === m ? 'bg-blue-600 text-white' : 'text-neutral-400'}`}>
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
