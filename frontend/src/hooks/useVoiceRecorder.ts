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

/**
 * MediaRecorder + OpenAI Whisper — działa na Chrome iOS, Firefox, Safari, Android.
 * Zastępuje Web Speech API które nie działa na Chrome/Firefox iOS.
 */
export function useVoiceRecorder(onResult?: (text: string) => void): UseVoiceRecorderReturn {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<VoiceError | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const isSupported =
    typeof window !== 'undefined' &&
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined';

  const stop = useCallback(() => {
    if (mediaRef.current && mediaRef.current.state !== 'inactive') {
      mediaRef.current.stop();
    }
  }, []);

  const start = useCallback(async () => {
    setError(null);
    chunksRef.current = [];

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
    } catch (e: any) {
      const name = e?.name ?? '';
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setError('not-allowed');
      } else {
        setError('unknown');
      }
      return;
    }

    // Wybierz format obsługiwany przez przeglądarkę
    const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg', 'audio/mp4']
      .find(t => MediaRecorder.isTypeSupported(t)) ?? '';

    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
    mediaRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      // Zatrzymaj mikrofon
      stream.getTracks().forEach(t => t.stop());
      streamRef.current = null;
      setIsListening(false);

      if (chunksRef.current.length === 0) {
        setError('no-speech');
        return;
      }

      const blob = new Blob(chunksRef.current, { type: mimeType || 'audio/webm' });
      chunksRef.current = [];

      setIsProcessing(true);
      try {
        const form = new FormData();
        form.append('audio', blob, `recording${mimeType.includes('ogg') ? '.ogg' : '.webm'}`);

        const res = await fetch(`${API_BASE}/voice/transcribe`, {
          method: 'POST',
          body: form,
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const text = (data.transcript ?? '').trim();

        if (!text) {
          setError('no-speech');
        } else {
          onResult?.(text);
        }
      } catch {
        setError('network');
      } finally {
        setIsProcessing(false);
      }
    };

    recorder.start();
    setIsListening(true);
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
