import React, { useState, useRef } from 'react';
import {
  Bot, BarChart3, Newspaper, Landmark, ShieldAlert, Map,
  CalendarDays, RotateCcw,
} from 'lucide-react';
import ChatInterface from '../../components/ChatInterface';
import { Chip, PageHead, Tag } from '../../components/simple/tv';
import { AppSection } from '../../types';

interface AssistantPageProps {
  initialQuery?: string;
  onNavigate?: (section: AppSection | 'logout') => void;
  onInitialQuerySent?: () => void;
}

interface AgentDef {
  id: string | null;
  label: string;
  desc: string;
  about: string;
  capabilities: string[];
  image: string | null;
  video: string | null;
  icon: React.ReactNode;
}

const AGENTS: AgentDef[] = [
  {
    id: null,
    label: 'Auto',
    desc: 'Automatyczny dobór agenta',
    about: 'System automatycznie rozpoznaje temat pytania i kieruje je do najlepszego agenta.',
    capabilities: ['Pytania ogólne', 'Automatyczny routing', 'Wszystkie tematy'],
    image: '/agents/auto-hero.webp',
    video: '/agents/auto.mp4',
    icon: <Bot size={22} />,
  },
  {
    id: 'redaktor',
    label: 'Redaktor',
    desc: 'Wiadomości i aktualności',
    about: 'Zna wszystkie lokalne artykuły, ogłoszenia i aktualności z gminy Rybno.',
    capabilities: ['Wiadomości lokalne', 'Ogłoszenia', 'Aktualności', 'Artykuły prasowe'],
    image: '/agents/redaktor-hero.webp',
    video: '/agents/redaktor.mp4',
    icon: <Newspaper size={22} />,
  },
  {
    id: 'urzednik',
    label: 'Urzędnik',
    desc: 'BIP, przetargi i urząd',
    about: 'Pomaga w sprawach urzędowych, przetargach, decyzjach i dokumentach BIP gminy.',
    capabilities: ['BIP i dokumenty', 'Przetargi', 'Procedury urzędowe', 'Zarządzenia'],
    image: '/agents/urzednik-hero.webp',
    video: '/agents/urzednik.mp4',
    icon: <Landmark size={22} />,
  },
  {
    id: 'straznik',
    label: 'Strażnik',
    desc: 'Awarie i bezpieczeństwo',
    about: 'Informuje o awariach sieci, alertach RCB, zagrożeniach i zdarzeniach kryzysowych.',
    capabilities: ['Awarie wody i prądu', 'Alerty RCB', 'Bezpieczeństwo', 'Zdarzenia drogowe'],
    image: '/agents/straznik-hero.webp',
    video: '/agents/straznik.mp4',
    icon: <ShieldAlert size={22} />,
  },
  {
    id: 'przewodnik',
    label: 'Przewodnik',
    desc: 'Wydarzenia i atrakcje',
    about: 'Doradza w kwestiach wydarzeń lokalnych, atrakcji turystycznych i prognozy pogody.',
    capabilities: ['Imprezy lokalne', 'Atrakcje turystyczne', 'Pogoda', 'Miejsca w gminie'],
    image: '/agents/przewodnik-hero.webp',
    video: '/agents/przewodnik.mp4',
    icon: <Map size={22} />,
  },
  {
    id: 'organizator',
    label: 'Organizator',
    desc: 'Śmieci i usługi',
    about: 'Zna pełny harmonogram odbioru odpadów w każdej miejscowości gminy Rybno na 2026 rok.',
    capabilities: ['Harmonogram śmieci', 'Segregacja odpadów', 'Punkty PSZOK', 'Usługi komunalne'],
    image: '/agents/organizator-hero.webp',
    video: '/agents/organizator.mp4',
    icon: <CalendarDays size={22} />,
  },
  {
    id: 'gus_analityk',
    label: 'GUS',
    desc: 'Statystyki i dane',
    about: 'Analizuje dane statystyczne GUS dotyczące gminy Rybno i powiatu działdowskiego.',
    capabilities: ['Dane demograficzne', 'Finanse gminy', 'Porównania krajowe', 'Trendy'],
    image: null,
    video: null,
    icon: <BarChart3 size={22} />,
  },
];

const AssistantPage: React.FC<AssistantPageProps> = ({ initialQuery, onNavigate, onInitialQuerySent }) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0);
  // Video ładuje się dopiero po pierwszym kliknięciu agenta — nie blokuje FCP
  const [videoEnabled, setVideoEnabled] = useState(false);
  const _videoRef = useRef<HTMLVideoElement>(null);

  const activeAgent = AGENTS.find(a => a.id === selectedAgentId) ?? AGENTS[0];

  const handleSelectAgent = (id: string | null) => {
    setSelectedAgentId(id);
    if (!videoEnabled) setVideoEnabled(true);
  };

  return (
    <div className="w-full pb-24">
      <ChatInterface
        key={chatKey}
        initialQuery={initialQuery}
        onNavigate={onNavigate}
        onInitialQuerySent={onInitialQuerySent}
        selectedAgent={selectedAgentId}
        headerContent={
          <div className="mx-auto w-full max-w-3xl space-y-4 px-4 pb-4 pt-4 md:px-8 md:pb-6 md:pt-8">
            {/* Jedna wyśrodkowana kolumna dla główki, rozmowy i pola (`ChatInterface`
                ma tę samą szerokość). Czat to rozmowa, nie lista — czyta się go
                w osi ekranu; do 11.10.2026 były tu trzy różne lewe krawędzie */}
            <PageHead
              title="Asystent"
              sub="Zadaj pytanie o gminę Rybno — wiadomości, urzędy, statystyki lub wydarzenia."
              aside={
                <button
                  onClick={() => setChatKey(k => k + 1)}
                  className="font-cond flex min-h-[44px] shrink-0 items-center gap-2 bg-tv-panel px-3 text-[15px] font-bold uppercase tracking-wide text-tv-paper transition-colors hover:bg-tv-panel2 hover:text-white"
                >
                  <RotateCcw size={16} aria-hidden />
                  Nowa rozmowa
                </button>
              }
            />

            {/* WYBÓR AGENTA — filtry jak w Wiadomościach; na telefonie przewijane w poziomie */}
            <div
              role="group"
              aria-label="Wybór agenta"
              className="-mx-4 flex gap-px overflow-x-auto px-4 no-scrollbar md:mx-0 md:flex-wrap md:px-0"
            >
              {AGENTS.map(agent => (
                <Chip
                  key={String(agent.id)}
                  active={selectedAgentId === agent.id}
                  onClick={() => handleSelectAgent(agent.id)}
                >
                  {agent.label}
                </Chip>
              ))}
            </div>

            {/* KARTA AGENTA — zdjęcie (albo wideo po pierwszym wyborze) obok opisu.
                Kwadrat zamiast ekranu na pół strony: na telefonie czat ma zaczynać
                się nad zgięciem, a nie pod portretem. */}
            <section aria-label={`Agent: ${activeAgent.label}`} className="flex flex-col">
              {/* Plakietka mówi rolę, nie powtarza nazwy z aktywnego filtra („AUTO” nad „AUTO”) */}
              <Tag as="h2">Kto odpowiada</Tag>
              <div className="flex gap-4 border-t-2 border-tv-blue bg-tv-panel p-3 md:p-4">
                {/* Portret od `md`: na telefonie 360 px pierwszy ekran ma należeć
                    do rozmowy, nie do zdjęcia agenta */}
                <div className="hidden h-40 w-40 shrink-0 overflow-hidden bg-tv-panel2 md:block">
                  {videoEnabled && activeAgent.video ? (
                    <video
                      key={activeAgent.video}
                      ref={_videoRef}
                      src={activeAgent.video}
                      autoPlay
                      loop
                      muted
                      playsInline
                      preload="none"
                      className="block h-full w-full object-cover object-[center_20%]"
                    />
                  ) : activeAgent.image ? (
                    <img
                      src={activeAgent.image}
                      alt={activeAgent.label}
                      loading="lazy"
                      decoding="async"
                      className="block h-full w-full object-cover object-[center_20%]"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-tv-muted">
                      {React.cloneElement(activeAgent.icon as React.ReactElement<{ size?: number }>, { size: 40 })}
                    </div>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-cond text-[19px] font-extrabold leading-tight text-white">{activeAgent.desc}</p>
                  <p className="mt-1 hidden max-w-[65ch] text-[15px] leading-snug text-[#d7dbe8] md:block">{activeAgent.about}</p>
                  <ul className="mt-2 hidden flex-wrap gap-x-4 gap-y-1 text-[13px] text-tv-muted md:flex">
                    {activeAgent.capabilities.map((cap, i) => (
                      <li key={i}>{cap}</li>
                    ))}
                  </ul>
                  <p className="mt-2 hidden text-[13px] text-tv-muted md:block">Odpowiada model OpenAI na danych gminy</p>
                </div>
              </div>
            </section>
          </div>
        }
      />
    </div>
  );
};

export default AssistantPage;
