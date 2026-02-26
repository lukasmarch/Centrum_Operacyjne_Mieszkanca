import React from 'react';
import { Activity } from 'lucide-react';

const GminaMonitoringTile: React.FC = () => {
    return (
        <div className="h-full flex flex-col justify-end p-5 relative overflow-hidden rounded-3xl bg-slate-900 border border-slate-800 group cursor-pointer hover:border-blue-500/30 transition-colors">
            {/* Background Image Setup */}
            {/* W tym miejscu mozna podstawic faktycznie podane przez usera zdjecie wgrywając je do public/ */}
            {/* Uzywamy gradientu aby zapewnic czarny overlay pod tekst */}
            <div
                className="absolute inset-0 bg-cover bg-center opacity-40 group-hover:opacity-50 transition-opacity duration-500 grayscale mix-blend-overlay"
                style={{
                    backgroundImage: `url('https://images.unsplash.com/photo-1544640808-32cbef10ca5b?q=80&w=600&auto=format&fit=crop')`,
                }}
            ></div>

            <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent"></div>

            {/* Content that goes over the overlay */}
            <div className="relative z-10">
                <div className="flex items-center gap-2 mb-1">
                    <Activity size={16} className="text-blue-500" />
                    <h3 className="text-lg font-bold text-slate-100 group-hover:text-blue-400 transition-colors">Monitoring Gminy</h3>
                </div>
                <p className="text-xs text-slate-400">Aktywne zgłoszenia: 3</p>
            </div>
        </div>
    );
};

export default GminaMonitoringTile;
