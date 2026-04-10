import { useSpeechRecognition } from './useSpeechRecognition';
import { useVoiceRecorder } from './useVoiceRecorder';

export type VoiceInputError = 'not-allowed' | 'no-speech' | 'network' | 'aborted' | 'unknown';

export interface UseVoiceInputReturn {
  isSupported: boolean;
  isListening: boolean;
  isProcessing: boolean;
  error: VoiceInputError | null;
  start: () => void;
  stop: () => void;
  clearError: () => void;
  /** true = używa Whisper (mobile), false = Web Speech API (desktop) */
  usesWhisper: boolean;
}

/**
 * Unified voice input hook.
 *
 * Strategia:
 *  - Desktop Chrome/Edge/Safari: Web Speech API (natychmiastowe, bezpłatne)
 *  - Chrome iOS, Firefox, inne: MediaRecorder + OpenAI Whisper
 *
 * Interfejs identyczny z useSpeechRecognition — komponenty wymagają
 * tylko zmiany importu.
 */
export function useVoiceInput(onResult?: (text: string) => void): UseVoiceInputReturn {
  const webSpeech = useSpeechRecognition(onResult);
  const whisper = useVoiceRecorder(onResult);

  // Używaj Whisper gdy Web Speech API niedostępne (Chrome iOS, Firefox)
  const useWhisper = !webSpeech.isSupported;

  if (useWhisper) {
    return {
      isSupported: whisper.isSupported,
      isListening: whisper.isListening,
      isProcessing: whisper.isProcessing,
      error: whisper.error,
      start: whisper.start,
      stop: whisper.stop,
      clearError: whisper.clearError,
      usesWhisper: true,
    };
  }

  return {
    isSupported: webSpeech.isSupported,
    isListening: webSpeech.isListening,
    isProcessing: false,
    error: webSpeech.error,
    start: webSpeech.start,
    stop: webSpeech.stop,
    clearError: webSpeech.clearError,
    usesWhisper: false,
  };
}
