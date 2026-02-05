import React, { useState } from 'react';
import { Search, Loader2, Building, AlertCircle } from 'lucide-react';

interface RegonResult {
    Nip: string;
    Regon: string;
    Nazwa: string;
    Wojewodztwo: string;
    Powiat: string;
    Gmina: string;
    Miejscowosc: string;
    Ulica: string;
    NrNieruchomosci: string;
}

const RegonSearchWidget: React.FC = () => {
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<RegonResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [searched, setSearched] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (query.length < 3) return;

        setLoading(true);
        setError(null);
        setResults([]);
        setSearched(false);

        try {
            // Determine parameter based on input format
            let param = "";
            let cleanQuery = query.replace(/-/g, "").trim();

            if (/^\d{10}$/.test(cleanQuery)) {
                param = `nip=${cleanQuery}`;
            } else if (/^\d{9}$/.test(cleanQuery) || /^\d{14}$/.test(cleanQuery)) {
                param = `regon=${cleanQuery}`;
            } else {
                param = `nazwa=${encodeURIComponent(query)}`;
            }

            const response = await fetch(`http://localhost:8000/api/business/regon-search?${param}`);

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Błąd wyszukiwania");
            }

            const data = await response.json();
            setResults(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
            setSearched(true);
        }
    };

    return (
        <div className="bg-white rounded-3xl p-6 border border-slate-100 shadow-sm h-full flex flex-col">
            <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                <span className="p-2 bg-indigo-50 text-indigo-600 rounded-xl">🔍</span>
                Wyszukiwarka REGON
            </h3>

            <form onSubmit={handleSearch} className="mb-4">
                <div className="relative">
                    <input
                        type="text"
                        placeholder="NIP, REGON lub Nazwa..."
                        className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                    <Search className="absolute left-3 top-3.5 w-4 h-4 text-slate-400" />
                    <button
                        type="submit"
                        disabled={loading || query.length < 3}
                        className="absolute right-2 top-2 p-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
                    >
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <span className="text-xs font-bold px-1">Szukaj</span>}
                    </button>
                </div>
                <p className="text-[10px] text-slate-400 mt-2 pl-1">
                    Dane bezpośrednio z bazy GUS (BIR1)
                </p>
            </form>

            <div className="flex-1 overflow-y-auto max-h-[300px] space-y-3 custom-scrollbar">
                {error && (
                    <div className="p-3 bg-red-50 text-red-600 text-sm rounded-xl flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        {error}
                    </div>
                )}

                {searched && results.length === 0 && !error && (
                    <div className="text-center text-slate-400 py-8 text-sm">
                        Brak wyników
                    </div>
                )}

                {results.map((item, idx) => (
                    <div key={idx} className="p-3 border border-slate-100 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors">
                        <div className="flex items-start justify-between mb-1">
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                                {item.Miejscowosc}
                            </span>
                            {item.Nip && (
                                <span className="text-[10px] bg-white border border-slate-200 px-1.5 py-0.5 rounded text-slate-500">
                                    NIP: {item.Nip}
                                </span>
                            )}
                        </div>
                        <h4 className="text-sm font-bold text-slate-900 leading-tight mb-1">
                            {item.Nazwa}
                        </h4>
                        <p className="text-xs text-slate-500 flex items-center gap-1">
                            <Building className="w-3 h-3" />
                            {item.Ulica} {item.NrNieruchomosci}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default RegonSearchWidget;
