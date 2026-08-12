import React, { useState } from 'react';
import { Image as ImageIcon } from 'lucide-react';

interface WeekendCardProps {
    subtitle: string;
    onClick: () => void;
    /** Własne zdjęcie okolicy — public/simple/weekend.jpg; brak pliku = podkład */
    imageSrc?: string;
}

/**
 * Karta weekendowa — jedyne miejsce trybu prostego z dużym obrazem.
 * Zdjęcia źródeł zewnętrznych są objęte prawami autorskimi (brief §5),
 * więc slot przyjmuje wyłącznie własną fotografię gminy; dopóki jej nie ma,
 * pokazuje spokojny podkład — nigdy pustą ramkę.
 */
const WeekendCard: React.FC<WeekendCardProps> = ({ subtitle, onClick, imageSrc = '/simple/weekend.jpg' }) => {
    const [imageOk, setImageOk] = useState(true);

    return (
        <button
            onClick={onClick}
            className="block w-full overflow-hidden rounded-2xl border border-white/10 bg-[#0d1117] text-left transition-colors hover:border-white/20"
        >
            <div className="relative h-44 lg:h-56 w-full bg-gradient-to-br from-[#101a33] to-[#0d1117]">
                {imageOk ? (
                    <img
                        src={imageSrc}
                        alt=""
                        loading="lazy"
                        onError={() => setImageOk(false)}
                        className="h-full w-full object-cover"
                    />
                ) : (
                    <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-blue-300/50">
                        <ImageIcon size={32} aria-hidden />
                        <span className="text-xs">własne zdjęcie okolicy</span>
                    </div>
                )}
            </div>
            <div className="p-5">
                <h3 className="text-lg font-bold text-white">Co w ten weekend?</h3>
                <p className="mt-1 text-sm text-neutral-400">{subtitle}</p>
            </div>
        </button>
    );
};

export default WeekendCard;
