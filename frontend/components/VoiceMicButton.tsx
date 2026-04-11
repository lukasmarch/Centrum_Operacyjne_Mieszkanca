/**
 * VoiceMicButton — przycisk mikrofonu działający na wszystkich przeglądarkach.
 *
 * Desktop Chrome/Edge/Safari → Web Speech API (natychmiastowe, bezpłatne)
 * Chrome iOS / Firefox iOS   → <label>+<input file capture> → Whisper
 *   (Apple blokuje programatyczny .click() na file input — label jest jedynym
 *    sposobem na wywołanie natywnego rejestratora iOS z poziomu przeglądarki)
 */
import React, { useState, useId } from 'react';
import { Mic, MicOff, Loader2 } from 'lucide-react';
import type { UseVoiceInputReturn } from '../src/hooks/useVoiceInput';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api';

interface Props {
  speech: UseVoiceInputReturn;
  onTranscript: (text: string) => void;
  /** klasy CSS dla przycisku / labela */
  className?: string;
  iconSize?: number;
}

export const VoiceMicButton: React.FC<Props> = ({
  speech,
  onTranscript,
  className = '',
  iconSize = 16,
}) => {
  const inputId = useId();
  const [fileProcessing, setFileProcessing] = useState(false);
  const [fileError, setFileError] = useState(false);

  if (!speech.isSupported) return null;

  // ── Ścieżka iOS: file input (Chrome iOS, Firefox iOS) ──────────────────────
  if (speech.usesWhisper) {
    const isProc = fileProcessing;

    const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      e.target.value = '';           // reset — żeby można nagrać jeszcze raz
      if (!file) return;

      setFileError(false);
      setFileProcessing(true);
      try {
        const form = new FormData();
        form.append('audio', file, file.name);
        const res = await fetch(`${API_BASE}/voice/transcribe`, {
          method: 'POST',
          body: form,
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        const text = (data.transcript ?? '').trim();
        if (text) onTranscript(text);
        else setFileError(true);
      } catch {
        setFileError(true);
      } finally {
        setFileProcessing(false);
      }
    };

    return (
      <>
        {/* Ukryty input — dostępny przez label (tap bezpośredni, iOS go akceptuje) */}
        <input
          id={inputId}
          type="file"
          accept="audio/*,video/mp4"
          capture="microphone"
          onChange={handleFile}
          disabled={isProc}
          style={{ position: 'fixed', top: -9999, left: -9999, opacity: 0, width: 1, height: 1 }}
        />
        <label
          htmlFor={inputId}
          className={`cursor-pointer select-none ${className} ${fileError ? 'text-amber-500' : ''}`}
          title={isProc ? 'Przetwarzam...' : 'Nagraj wiadomość głosową'}
          aria-label="Mikrofon"
        >
          {isProc
            ? <Loader2 size={iconSize} className="animate-spin text-blue-400" />
            : <Mic size={iconSize} />}
        </label>
      </>
    );
  }

  // ── Ścieżka desktop: Web Speech API ────────────────────────────────────────
  const hasError = speech.error === 'not-allowed';
  return (
    <button
      type="button"
      onClick={() => speech.isListening ? speech.stop() : speech.start()}
      disabled={speech.isProcessing}
      title={
        hasError
          ? 'Brak dostępu do mikrofonu — zezwól w ustawieniach przeglądarki'
          : speech.isProcessing ? 'Przetwarzam...'
          : speech.isListening ? 'Zatrzymaj nagrywanie'
          : 'Mów do mikrofonu'
      }
      className={`${className} ${hasError ? 'text-amber-500' : ''}`}
      aria-label="Mikrofon"
    >
      {speech.isProcessing
        ? <Loader2 size={iconSize} className="animate-spin text-blue-400" />
        : speech.isListening
        ? <MicOff size={iconSize} />
        : <Mic size={iconSize} />}
    </button>
  );
};
