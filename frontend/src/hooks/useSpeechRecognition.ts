import { useState, useRef, useCallback } from 'react';

export type SpeechError = 'not-allowed' | 'no-speech' | 'network' | 'aborted' | 'unknown';

interface UseSpeechRecognitionReturn {
  isSupported: boolean;
  isListening: boolean;
  transcript: string;
  error: SpeechError | null;
  start: () => void;
  stop: () => void;
  clearError: () => void;
}

export function useSpeechRecognition(onResult?: (text: string) => void): UseSpeechRecognitionReturn {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<SpeechError | null>(null);
  const recRef = useRef<any>(null);

  // synchronous — no useEffect flash
  const isSupported = typeof window !== 'undefined' &&
    !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  const stop = useCallback(() => {
    recRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;

    setError(null);
    const recognition = new SR();
    recognition.lang = 'pl-PL';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    recognition.onstart = () => setIsListening(true);

    recognition.onresult = (e: any) => {
      const text = e.results[0][0].transcript;
      setTranscript(text);
      onResult?.(text);
    };

    recognition.onerror = (e: any) => {
      const code = e.error as string;
      if (code === 'not-allowed' || code === 'permission-denied') {
        setError('not-allowed');
      } else if (code === 'no-speech') {
        setError('no-speech');
      } else if (code === 'network') {
        setError('network');
      } else if (code === 'aborted') {
        setError('aborted');
      } else {
        setError('unknown');
      }
      setIsListening(false);
    };

    recognition.onend = () => setIsListening(false);

    recRef.current = recognition;
    recognition.start();
  }, [onResult]);

  return { isSupported, isListening, transcript, error, start, stop, clearError: () => setError(null) };
}
