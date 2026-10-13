import React, { useState } from 'react';
import {
  Check, ThumbsUp, ThumbsDown, CornerDownRight, SearchX, AlertTriangle, Info,
  ArrowUp, ArrowDown, Droplets, ChevronDown,
} from 'lucide-react';
import { Tag } from './simple/tv';
import { AgentStep, ChatMessageData, ChartConfig, sendChatFeedback } from '../src/hooks/useChat';
import SourceChip from './SourceChip';
import TrendChart from './gus/charts/TrendChart';

interface ChatMessageProps {
  message: ChatMessageData;
  /** Klik w chip pytania pomocniczego — wysyła je jako nową wiadomość */
  onFollowUp?: (question: string) => void;
  /** Chipy pytań pomocniczych pokazujemy tylko przy ostatniej odpowiedzi */
  showFollowups?: boolean;
}

// Plakietka agenta nad odpowiedzią — nazwa zamiast awatara (odświeżenie 10.2026).
//
// Do 10.2026 stały tu awatary: miniatury `-thumb` z frontend/public/agents/
// (20.08.2026 zastąpiły plik 2752×1536 i 5,8 MB wstawiany w kółko 32 px).
// W „Pasku informacyjnym” mówiącego przedstawia plakietka tematu, jak w grafice
// telewizji — zdjęcie agenta zostało tylko w karcie nad czatem (AssistantPage).
const AGENT_LABELS: Record<string, string> = {
  redaktor: 'Redaktor',
  urzednik: 'Urzędnik',
  straznik: 'Strażnik',
  przewodnik: 'Przewodnik',
  organizator: 'Organizator',
  gus_analityk: 'GUS-Analityk',
  koordynator: 'Koordynator',
};

// ── Markdown renderer ──────────────────────────────────────────────────────

/**
 * Wyróżniki odpowiedzi w żółci (decyzja Łukasza 11.10.2026). Żółć w tym świecie
 * znaczy kontekst i zapowiedź — w odpowiedzi to FAKT-KOTWICA: termin, godzina,
 * wieś, kwota. Waga 700 zostaje drugim nośnikiem — sam odcień nie wystarczy
 * przy deuteranopii.
 *
 * Do 13.10 żółte były tylko TRZY pierwsze pogrubienia na odpowiedź. W liście
 * pięciu wydarzeń dawało to dwie pozycje żółte i trzy białe — czytelnik brał
 * to za różnicę ważności (uwaga Łukasza). Teraz żółte jest każde pogrubienie,
 * a bezpiecznikiem przeciw „pół akapitu na żółto” jest DŁUGOŚĆ: kotwica to
 * termin, nazwa, kwota — dłuższe pogrubienie zostaje białe.
 */
const MAX_ANCHOR_CHARS = 60;
/** Ile terminów wyróżnia `autoAnchors`, gdy model sam nic nie pogrubił */
const MAX_AUTO_ANCHORS = 3;

// Termin w odpowiedzi: „14 października 2026 roku”, „14.10”, „9:00–13:00”, „dziś”, „jutro”
const MONTHS_GEN = 'stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia';
const ANCHOR_RE = new RegExp(
  `\\b\\d{1,2} (?:${MONTHS_GEN})(?: \\d{4})?(?: r(?:oku|\\.))?|\\b\\d{1,2}\\.\\d{2}(?:\\.\\d{4})?\\b|\\b\\d{1,2}:\\d{2}(?:\\s?[–-]\\s?\\d{1,2}:\\d{2})?|(?<!\\p{L})(?:dziś|dzisiaj|jutro|pojutrze)(?!\\p{L})`,
  // `u`: `\b` w JS zna tylko litery ASCII — „dziś” przed spacją nie miało granicy słowa
  'giu',
);

/**
 * Model rzadko sam pogrubia (pomiar 11.10: 0 pogrubień w odpowiedziach o wywozie,
 * mimo reguły w `base_agent.COMPLETENESS`). Regułę sprawdzalną kodem sprawdza kod:
 * gdy w odpowiedzi nie ma ani jednego `**`, wyróżniamy pierwsze trzy TERMINY —
 * jedyny rodzaj kotwicy, który da się rozpoznać bez zgadywania (wieś czy kwota już nie).
 */
function autoAnchors(text: string): string {
  if (text.includes('**')) return text;
  let n = 0;
  return text.replace(ANCHOR_RE, m => (n++ < MAX_AUTO_ANCHORS ? `**${m}**` : m));
}

function renderMarkdown(raw: string): React.ReactNode {
  const text = autoAnchors(raw);
  const paragraphs = text.split(/\n\n+/);
  // Numeracja listy biegnie PRZEZ akapity: model oddziela pozycje pustą linią,
  // a każdy akapit stawał się osobną listą od „1.” (13.10 — pięć razy „1.”).
  // Licznik zeruje dopiero treść, która nie jest pozycją listy numerowanej
  let olCount = 0;
  return paragraphs.map((para, pi) => {
    const lines = para.split('\n');
    const nodes: React.ReactNode[] = [];
    let listItems: React.ReactNode[] = [];
    let ordered = false;

    const flushList = () => {
      if (listItems.length > 0) {
        const cls = 'my-2 space-y-1.5 pl-5 marker:text-tv-muted';
        nodes.push(ordered
          ? <ol key={`ol-${pi}-${nodes.length}`} start={olCount - listItems.length + 1} className={`list-decimal ${cls} marker:tabular`}>{listItems}</ol>
          : <ul key={`ul-${pi}-${nodes.length}`} className={`list-disc ${cls}`}>{listItems}</ul>);
        listItems = [];
      }
    };

    lines.forEach((line, li) => {
      const headingMatch = line.match(/^(#{1,4})\s+(.+)/);
      const listMatch = line.match(/^[-•*]\s+(.+)/);
      const numberedMatch = line.match(/^\d+\.\s+(.+)/);

      if (headingMatch) {
        flushList();
        olCount = 0;
        nodes.push(
          <h3 key={`h-${pi}-${li}`} className="font-cond mb-1 mt-3 text-[18px] font-extrabold leading-tight text-white">
            {inlineMarkdown(headingMatch[2])}
          </h3>
        );
      } else if (listMatch || numberedMatch) {
        const isNum = !!numberedMatch;
        // Zmiana rodzaju listy w środku akapitu zamyka poprzednią
        if (listItems.length > 0 && isNum !== ordered) flushList();
        ordered = isNum;
        if (isNum) olCount += 1; else olCount = 0;
        listItems.push(
          <li key={`li-${pi}-${li}`}>
            {inlineMarkdown((numberedMatch ?? listMatch)![1])}
          </li>
        );
      } else if (line.trim()) {
        flushList();
        olCount = 0;
        nodes.push(<span key={`t-${pi}-${li}`}>{inlineMarkdown(line)}</span>);
        if (li < lines.length - 1) nodes.push(<br key={`br-${pi}-${li}`} />);
      }
    });

    flushList();
    if (nodes.length === 0) return null;
    return (
      // div, nie p: akapit z listą w środku to niepoprawny HTML (ul w p)
      <div key={`p-${pi}`} className="mb-3 last:mb-0">
        {nodes}
      </div>
    );
  });
}

function inlineMarkdown(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)]+\))/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      const highlight = part.length - 4 <= MAX_ANCHOR_CHARS;
      return (
        <strong key={i} className={`font-bold ${highlight ? 'text-tv-yellow' : 'text-white'}`}>
          {part.slice(2, -2)}
        </strong>
      );
    }
    const linkMatch = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
    if (linkMatch) {
      return (
        <a
          key={i}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-tv-bluesoft underline underline-offset-4 transition-colors hover:text-white"
        >
          {linkMatch[1]}
        </a>
      );
    }
    return part;
  });
}


// ── Mini KPI chart ─────────────────────────────────────────────────────────

const MiniKPI: React.FC<{ chart: ChartConfig }> = ({ chart }) => (
  <div className="flex items-center justify-between gap-4">
    <div className="min-w-0">
      <p className="mb-1 truncate text-[13px] text-tv-muted">{chart.title}</p>
      <p className="font-cond tabular text-[28px] font-extrabold leading-none text-white">
        {chart.current_value?.toLocaleString('pl-PL') ?? '—'}
      </p>
      {chart.trend_pct !== null && chart.trend_pct !== undefined && (
        <p className="tabular mt-1 inline-flex items-center gap-1 text-[13px] text-tv-paper">
          {chart.trend_pct >= 0 ? <ArrowUp size={13} aria-hidden /> : <ArrowDown size={13} aria-hidden />}
          {Math.abs(chart.trend_pct)}% r/r
        </p>
      )}
    </div>
    {chart.national_value !== undefined && (
      <div className="shrink-0 text-right">
        <p className="text-[13px] text-tv-muted">Śr. krajowa</p>
        <p className="tabular text-[15px] text-tv-paper">{chart.national_value?.toLocaleString('pl-PL')}</p>
        <p className="tabular text-[13px] text-tv-muted">{chart.year}</p>
      </div>
    )}
  </div>
);

// ── Kroki pracy agenta ─────────────────────────────────────────────────────

/**
 * Jeden krok pracy agenta: co sprawdza, czego szuka, co zastał.
 *
 * Po co to widać. Do 22.08 agent milczał przez półtorej sekundy, a potem
 * pisał odpowiedź — użytkownik nie wiedział ani czy system go zrozumiał, ani
 * na czym stoi odpowiedź. Teraz widzi „Sprawdzam harmonogram wywozu ·
 * Hartowiec", więc gdy padnie tam zła miejscowość, poprawia pytanie od razu,
 * zamiast czytać do końca coś nie na temat.
 *
 * Stan pustego wyniku ma osobną ikonę i osobny kolor, bo to inna wiadomość niż
 * „gotowe": agent sprawdził i NIE ZNALAZŁ, więc odpowiedź poniżej będzie
 * ostrożna — i wiadomo dlaczego.
 */
const STEP_ICONS: Record<string, React.ReactNode> = {
  done: <Check size={14} className="text-tv-green shrink-0" />,
  empty: <SearchX size={14} className="text-tv-yellow shrink-0" />,
  error: <AlertTriangle size={14} className="text-tv-red shrink-0" />,
  warning: <AlertTriangle size={14} className="text-tv-yellow shrink-0" />,
  info: <Info size={14} className="text-tv-muted shrink-0" />,
};

/** „straznik”, „Straznik.ai” → „Strażnik” — kroki pokazywały identyfikatory z kodu. */
const humanize = (text?: string) =>
  (text ?? '').replace(/\b(straznik|organizator|urzednik|redaktor|przewodnik|koordynator|gus_analityk)(\.ai)?\b/gi,
    (_, id: string) => AGENT_LABELS[id.toLowerCase()] ?? id);

const AgentStepRow: React.FC<{
  step: AgentStep;
  isLast: boolean;
  isStreaming: boolean;
  hasContent: boolean;
}> = ({ step, isLast, isStreaming, hasContent }) => {
  // „W toku" pokazujemy tylko dopóki naprawdę trwa: po dojściu treści albo po
  // zamknięciu strumienia kręcące się kółko kłamałoby.
  //
  // ⚠️ `isStreaming` obowiązuje TAKŻE kroki z jawnym `state: "running"`. Bez tego
  // warunku krok, którego nikt nie domknął, kręcił się po gotowej odpowiedzi —
  // tak wyszło 31.08 ze zdarzeniem handoffu (przychodzi jako „running" i bez
  // `tool`, więc dopasowanie po nazwie narzędzia go nie zamykało). `useChat`
  // domyka je teraz w danych; to jest druga bramka, na wypadek kolejnego kroku,
  // który o domknięciu zapomni.
  const spinning =
    isStreaming &&
    (step.state === 'running' || (!hasContent && isLast && !step.state));

  return (
    <div className="flex items-start gap-2 text-[13px] leading-snug">
      <span className="mt-[2px] flex h-3.5 w-3.5 shrink-0 items-center justify-center">
        {spinning ? (
          // „W toku": kwadrat w chabrze, ten sam stan co plakietka tematu
          <span aria-label="w toku" className="block h-2 w-2 animate-pulse bg-tv-bluesoft" />
        ) : (
          STEP_ICONS[step.state || 'info'] ?? STEP_ICONS.info
        )}
      </span>
      <span className="min-w-0">
        <span className={step.state === 'error' ? 'text-tv-red' : 'text-tv-muted'}>
          {humanize(step.message)}
        </span>
        {step.detail && (
          <span className="text-tv-muted"> · {humanize(step.detail)}</span>
        )}
        {step.result && (
          <span
            className={
              step.state === 'empty'
                ? 'text-tv-yellow'
                : step.state === 'error'
                ? 'text-tv-red'
                : 'text-tv-muted'
            }
          >
            {' '}→ {humanize(step.result)}
          </span>
        )}
      </span>
    </div>
  );
};

// ── Pasek prognozy ─────────────────────────────────────────────────────────

/**
 * Prognoza pod odpowiedzią Przewodnika — dane z narzędzia `weather_forecast`.
 *
 * Model opisuje pogodę słowami, ale „18 stopni i mała szansa deszczu" czyta się
 * gorzej niż trzy kafelki obok siebie. Liczby idą TU, nie przez tekst modelu:
 * to, czego model nie musi przepisywać, nie może przekręcić.
 *
 * Ikony z tego samego źródła co WeatherTile, żeby prognoza w czacie i na
 * stronie głównej nie wyglądały jak dwa różne serwisy.
 */
const ForecastStrip: React.FC<{ chart: ChartConfig }> = ({ chart }) => {
  const days = chart.days ?? [];
  if (days.length === 0) return null;

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <p className="truncate text-[13px] text-tv-muted">{chart.title}</p>
        {chart.uv_index != null && (
          <p className="tabular shrink-0 text-[13px] text-tv-muted">
            UV {Math.round(chart.uv_index)}
          </p>
        )}
      </div>
      <div className="flex gap-px overflow-x-auto bg-tv-seam">
        {days.map((day, i) => (
          <div
            key={i}
            className="min-w-[96px] flex-1 bg-tv-panel2 px-3 py-2 text-center"
          >
            <p className="font-cond truncate text-[15px] font-bold capitalize text-white">
              {day.dzien}
            </p>
            <p className="tabular mb-1 text-[13px] text-tv-muted">{day.data.slice(0, 5)}</p>
            {day.icon && (
              <img
                src={`https://openweathermap.org/img/wn/${day.icon}@2x.png`}
                alt=""
                className="mx-auto h-10 w-10 object-contain"
              />
            )}
            <p className="font-cond tabular text-[17px] leading-tight text-white">
              <span className="font-extrabold">{Math.round(day.temp_max_c)}°</span>
              <span className="text-tv-muted"> / {Math.round(day.temp_min_c)}°</span>
            </p>
            <p className="truncate text-[13px] text-tv-muted" title={day.opis}>
              {day.opis}
            </p>
            {day.szansa_opadow_proc > 0 && (
              <p className="tabular mt-0.5 inline-flex items-center gap-1 text-[13px] text-tv-paper">
                <Droplets size={13} aria-hidden /> {day.szansa_opadow_proc}%
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Oceny 👍/👎 ────────────────────────────────────────────────────────────

const FeedbackButtons: React.FC<{ dbId: number }> = ({ dbId }) => {
  const [rated, setRated] = useState<1 | -1 | null>(null);

  const rate = (rating: 1 | -1) => {
    setRated(rating);
    sendChatFeedback(dbId, rating);
  };

  if (rated) {
    return (
      <p className="mt-2 flex min-h-[44px] items-center text-[13px] text-tv-muted">
        {rated === 1 ? 'Dziękujemy za ocenę!' : 'Dzięki — poprawimy się.'}
      </p>
    );
  }
  return (
    <div className="mt-2 flex items-center gap-1">
      <span className="mr-1 text-[13px] text-tv-muted">Czy ta odpowiedź pomogła?</span>
      <button
        onClick={() => rate(1)}
        aria-label="Odpowiedź pomogła"
        className="flex h-11 w-11 items-center justify-center text-tv-muted transition-colors hover:bg-tv-panel hover:text-white"
      >
        <ThumbsUp size={16} />
      </button>
      <button
        onClick={() => rate(-1)}
        aria-label="Odpowiedź nie pomogła"
        className="flex h-11 w-11 items-center justify-center text-tv-muted transition-colors hover:bg-tv-panel hover:text-white"
      >
        <ThumbsDown size={16} />
      </button>
    </div>
  );
};

// ── Main component ─────────────────────────────────────────────────────────

const ChatMessage: React.FC<ChatMessageProps> = ({ message, onFollowUp, showFollowups = true }) => {
  if (message.role === 'user') {
    // Pytanie mieszkańca: panel o stopień jaśniejszy, przy prawej krawędzi — bez dymka
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap bg-tv-panel2 px-4 py-3 text-[16px] leading-snug text-white md:max-w-[70%]">
          {message.content}
        </p>
      </div>
    );
  }

  const hasCharts = message.chartData && message.chartData.length > 0 && !message.isStreaming;
  const agentLabel = message.agent_name
    ? AGENT_LABELS[message.agent_name] ?? message.agent_name.replace('_', '-')
    : null;

  return (
    <article className="flex min-w-0 flex-col">
      {agentLabel && <Tag className="mb-2">{agentLabel}</Tag>}

      {/* Praca agenta: na żywo rozwinięta, po odpowiedzi zwinięta do jednej linii.
          Krytyka 11.10.2026: siedem wierszy kroków (w tym trzy „przekazuję dalej”)
          zostawało nad odpowiedzią na stałe i na telefonie spychało ją pod pole */}
      {message.steps && message.steps.length > 0 && (() => {
        const rows = (
          <div className="space-y-1 border-l border-tv-seam pl-3">
            {message.steps.map((step, i) => (
              <AgentStepRow
                key={i}
                step={step}
                isLast={i === message.steps!.length - 1}
                isStreaming={!!message.isStreaming}
                hasContent={!!message.content}
              />
            ))}
          </div>
        );
        if (message.isStreaming) return <div className="mb-3">{rows}</div>;
        const checked = message.steps.filter(st => st.tool && st.state !== 'running').length || message.steps.length;
        return (
          <details className="group mb-3">
            <summary className="flex min-h-[44px] cursor-pointer list-none items-center gap-2 text-[13px] text-tv-muted hover:text-white [&::-webkit-details-marker]:hidden">
              <Check size={14} className="shrink-0 text-tv-green" aria-hidden />
              Jak powstała odpowiedź: <span className="tabular">{checked}</span> {checked === 1 ? 'sprawdzenie' : checked < 5 ? 'sprawdzenia' : 'sprawdzeń'}
              <ChevronDown size={14} aria-hidden className="text-tv-bluesoft transition-transform group-open:rotate-180" />
            </summary>
            {rows}
          </details>
        );
      })()}

      {/* 62ch: `ch` liczy się od cyfry „0”, polski tekst w Archivo jest węższy —
          70ch dawało ~85 znaków w wierszu (pomiar 11.10.2026) */}
      <div className="max-w-[62ch] text-[16px] leading-[1.6] text-[#d7dbe8]">
        {message.content ? (
          <>
            <div>{renderMarkdown(message.content)}</div>
            {message.isStreaming && (
              <span aria-hidden className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-tv-bluesoft align-middle" />
            )}
          </>
        ) : message.isStreaming ? (
          <p className="text-[15px] text-tv-muted">Wczytuję…</p>
        ) : null}
      </div>

      {hasCharts && (
        <div className="mt-4 space-y-px">
          {message.chartData!.map((chart, i) => (
            <div key={i} className="overflow-hidden border-t-2 border-tv-blue bg-tv-panel px-4 py-3">
              {chart.chart_type === 'trend' && chart.data && chart.data.length >= 2 && (
                <TrendChart data={chart.data} title={chart.title} height={180} color="#8fa8ff" />
              )}
              {chart.chart_type === 'kpi' && <MiniKPI chart={chart} />}
              {chart.chart_type === 'forecast' && <ForecastStrip chart={chart} />}
            </div>
          ))}
        </div>
      )}

      {message.sources && message.sources.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-2">
          <span className="text-[13px] text-tv-muted">Źródła:</span>
          {message.sources.map((source, i) => (
            <SourceChip key={i} source={source} />
          ))}
        </div>
      )}

      {/* Ocena odpowiedzi — po zapisaniu wiadomości w bazie */}
      {!message.isStreaming && message.content && message.dbId && (
        <FeedbackButtons dbId={message.dbId} />
      )}

      {/* Pytania pomocnicze — zachęta do kontynuowania rozmowy */}
      {showFollowups && !message.isStreaming && message.followups && message.followups.length > 0 && (
        <div className="mt-2 flex flex-col items-start gap-px">
          {message.followups.map((q, i) => (
            <button
              key={i}
              onClick={() => onFollowUp?.(q)}
              className="flex min-h-[44px] items-center gap-2 bg-tv-panel px-3 py-2 text-left text-[15px] leading-snug text-tv-paper transition-colors hover:bg-tv-panel2 hover:text-white"
            >
              <CornerDownRight size={14} className="shrink-0 text-tv-bluesoft" aria-hidden />
              {q}
            </button>
          ))}
        </div>
      )}
    </article>
  );
};

export default ChatMessage;
