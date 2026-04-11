import { useState, useRef, useCallback } from 'react';

export type VoiceError = 'not-allowed' | 'no-speech' | 'network' | 'unknown';

interface UseVoiceRecorderReturn {
  isSupported: boolean;
  isListening: boolean;
  isProcessing: boolean;
  error: VoiceError | null;
  start: () => void;
  stop: () => void;
  clearError: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL ?? '/api';

async function sendToWhisper(
  blob: Blob,
  filename: string,
  onResult?: (text: string) => void,
  setError?: (e: VoiceError) => void,
  setProcessing?: (v: boolean) => void,
) {
  setProcessing?.(true);
  try {
    const form = new FormData();
    form.append('audio', blob, filename);
    const res = await fetch(`${API_BASE}/voice/transcribe`, { method: 'POST', body: form });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const text = (data.transcript ?? '').trim();
    if (!text) setError?.('no-speech');
    else onResult?.(text);
  } catch {
    setError?.('network');
  } finally {
    setProcessing?.(false);
  }
}

/**
 * Nagrywanie audio → OpenAI Whisper.
 *
 * Strategia fallback (ważna kolejność):
 *  1. getUserMedia + MediaRecorder  → działa na desktop, Android, Safari iOS 14.3+
 *  2. <input type="file" capture="microphone"> → działa na Chrome iOS, Firefox iOS
 *     (otwiera natywny rejestrator iOS, plik trafia do Whisper)
 */
export function useVoiceRecorder(onResult?: (text: string) => void): UseVoiceRecorderReturn {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<VoiceError | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const isSupported = typeof window !== 'undefined' && typeof navigator !== 'undefined';

  const stop = useCallback(() => {
    if (mediaRef.current && mediaRef.current.state !== 'inactive') {
      mediaRef.current.stop();
    }
  }, []);

  // Musi być synchroniczna (nie async) żeby iOS nie utracił kontekstu user gesture
  const start = useCallback(() => {
    setError(null);
    chunksRef.current = [];

    // ── Ścieżka 1: getUserMedia (desktop, Android, Safari iOS) ──
    if (navigator.mediaDevices?.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
          streamRef.current = stream;

          const mimeType = [
            'audio/webm;codecs=opus', 'audio/webm',
            'audio/ogg;codecs=opus', 'audio/ogg', 'audio/mp4',
          ].find(t => MediaRecorder.isTypeSupported(t)) ?? '';

          const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
          mediaRef.current = recorder;

          recorder.ondataavailable = (e) => {
            if (e.data.size > 0) chunksRef.current.push(e.data);
          };

          recorder.onstop = async () => {
            stream.getTracks().forEach(t => t.stop());
            streamRef.current = null;
            setIsListening(false);

            if (chunksRef.current.length === 0) { setError('no-speech'); return; }

            const blob = new Blob(chunksRef.current, { type: mimeType || 'audio/webm' });
            chunksRef.current = [];
            await sendToWhisper(
              blob,
              `recording${mimeType.includes('ogg') ? '.ogg' : '.webm'}`,
              onResult, setError, setIsProcessing,
            );
          };

          recorder.start();
          setIsListening(true);
        })
        .catch((e: any) => {
          const name = e?.name ?? '';
          if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
            setError('not-allowed');
          } else {
            // getUserMedia niedostępne mimo że API istnieje — spróbuj file input
            triggerFileInput();
          }
        });
      return;
    }

    // ── Ścieżka 2: file input (Chrome iOS, Firefox iOS) ──
    triggerFileInput();

    function triggerFileInput() {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'audio/*,video/*';
      input.setAttribute('capture', 'microphone');
      // Musi być w DOM żeby iOS go zaakceptował
      input.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0';
      document.body.appendChild(input);

      input.onchange = async () => {
        document.body.removeChild(input);
        const file = input.files?.[0];
        if (!file) { setError('no-speech'); return; }
        await sendToWhisper(file, file.name, onResult, setError, setIsProcessing);
      };

      input.oncancel = () => {
        document.body.removeChild(input);
      };

      input.click();
    }
  }, [onResult]);

  return {
    isSupported,
    isListening,
    isProcessing,
    error,
    start,
    stop,
    clearError: () => setError(null),
  };
}
