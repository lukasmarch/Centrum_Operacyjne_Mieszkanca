/**
 * Błąd z backendu w postaci, którą da się pokazać mieszkańcowi.
 *
 * Do 11.10.2026 formularz rejestracji pokazywał „[object Object]” (audyt F-036):
 * FastAPI przy błędzie walidacji oddaje `detail` jako LISTĘ obiektów
 * `{loc, msg, type}`, a `new Error(error.detail)` robiło z niej napis.
 * Gdy `detail` był tekstem, był po angielsku („Email already registered”).
 *
 * `fields` niesie komunikat przy konkretnym polu formularza (klucz = nazwa
 * pola w body), `message` — jedno zdanie ogólne nad formularzem.
 */
export class ApiError extends Error {
  fields: Record<string, string>;
  status: number;

  constructor(message: string, status: number, fields: Record<string, string> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
  }
}

// Teksty, które backend oddaje po angielsku — tłumaczenie tutaj, bo te same
// komunikaty czyta też API (i testy), a front jest jedynym miejscem dla ludzi
const KNOWN_DETAILS: Record<string, { message: string; field?: string }> = {
  'Email already registered': {
    message: 'Ten adres ma już konto. Zaloguj się albo użyj innego adresu.',
    field: 'email',
  },
  'Invalid email or password': { message: 'Nieprawidłowy e-mail lub hasło.' },
  'Account is inactive': { message: 'To konto jest nieaktywne. Napisz do nas, jeśli to pomyłka.' },
};

const FIELD_MESSAGES: Record<string, (type: string, msg: string) => string> = {
  email: () => 'Podaj poprawny adres e-mail, np. jan@poczta.pl.',
  full_name: (type) =>
    type === 'string_too_long' ? 'Imię i nazwisko może mieć najwyżej 100 znaków.' : 'Podaj imię i nazwisko (min. 2 znaki).',
  password: (type, msg) => {
    if (type === 'string_too_short') return 'Hasło musi mieć minimum 8 znaków.';
    if (type === 'string_too_long') return 'Hasło może mieć najwyżej 100 znaków.';
    if (/digit/i.test(msg)) return 'Hasło musi zawierać cyfrę.';
    if (/uppercase/i.test(msg)) return 'Hasło musi zawierać wielką literę.';
    return 'Hasło nie spełnia wymagań: min. 8 znaków, wielka litera i cyfra.';
  },
};
// Reset i zmiana hasła wysyłają `new_password` — te same wymagania i komunikaty
FIELD_MESSAGES.new_password = FIELD_MESSAGES.password;

interface ValidationItem {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

/** Zamienia odpowiedź błędu z API na `ApiError` z polskimi komunikatami. */
export async function toApiError(response: Response, fallback: string): Promise<ApiError> {
  let detail: unknown = null;
  try {
    detail = (await response.json())?.detail;
  } catch {
    // odpowiedź bez JSON-a (np. 502 z Caddy) — zostaje komunikat ogólny
  }

  if (Array.isArray(detail)) {
    const fields: Record<string, string> = {};
    for (const item of detail as ValidationItem[]) {
      const field = String(item.loc?.[item.loc.length - 1] ?? '');
      const translate = FIELD_MESSAGES[field];
      if (translate && !fields[field]) fields[field] = translate(item.type ?? '', item.msg ?? '');
    }
    const message = Object.keys(fields).length ? 'Popraw zaznaczone pola.' : fallback;
    return new ApiError(message, response.status, fields);
  }

  if (typeof detail === 'string' && detail) {
    const known = KNOWN_DETAILS[detail];
    if (known) {
      return new ApiError(known.message, response.status, known.field ? { [known.field]: known.message } : {});
    }
    return new ApiError(detail, response.status);
  }

  return new ApiError(fallback, response.status);
}
