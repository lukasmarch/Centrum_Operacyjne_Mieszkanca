import React, { useState } from 'react';
import {
  Bot, BarChart3, Newspaper, Landmark, ShieldAlert, Map,
  CalendarDays, RotateCcw, SlidersHorizontal, Info, ChevronRight,
} from 'lucide-react';
import ChatInterface from '../../components/ChatInterface';
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
  color: string;
}

const AGENTS: AgentDef[] = [
  {
    id: null,
    label: 'Auto',
    desc: 'Automatyczny dobór agenta',
    about: 'System automatycznie rozpoznaje temat pytania i kieruje je do najlepszego agenta.',
    capabilities: ['Pytania ogólne', 'Automatyczny routing', 'Wszystkie tematy'],
    image: '/agents/auto.jpeg',
    video: '/agents/auto.mp4',
    icon: <Bot size={22} />,
    color: 'from-blue-600 to-violet-600',
  },
  {
    id: 'redaktor',
    label: 'Redaktor',
    desc: 'Wiadomości i aktualności',
    about: 'Zna wszystkie lokalne artykuły, ogłoszenia i aktualności z gminy Rybno.',
    capabilities: ['Wiadomości lokalne', 'Ogłoszenia', 'Aktualności', 'Artykuły prasowe'],
    image: '/agents/redaktor.png',
    video: '/agents/redaktor.mp4',
    icon: <Newspaper size={22} />,
    color: 'from-sky-500 to-blue-700',
  },
  {
    id: 'urzednik',
    label: 'Urzędnik',
    desc: 'BIP, przetargi i urząd',
    about: 'Pomaga w sprawach urzędowych, przetargach, decyzjach i dokumentach BIP gminy.',
    capabilities: ['BIP i dokumenty', 'Przetargi', 'Procedury urzędowe', 'Zarządzenia'],
    image: '/agents/urzednik.jpeg',
    video: '/agents/urzednik.mp4',
    icon: <Landmark size={22} />,
    color: 'from-amber-500 to-orange-700',
  },
  {
    id: 'straznik',
    label: 'Strażnik',
    desc: 'Awarie i bezpieczeństwo',
    about: 'Informuje o awariach sieci, alertach RCB, zagrożeniach i zdarzeniach kryzysowych.',
    capabilities: ['Awarie wody i prądu', 'Alerty RCB', 'Bezpieczeństwo', 'Zdarzenia drogowe'],
    image: '/agents/straznik.jpeg',
    video: '/agents/straznik.mp4',
    icon: <ShieldAlert size={22} />,
    color: 'from-red-500 to-rose-700',
  },
  {
    id: 'przewodnik',
    label: 'Przewodnik',
    desc: 'Wydarzenia i atrakcje',
    about: 'Doradza w kwestiach wydarzeń lokalnych, atrakcji turystycznych i prognozy pogody.',
    capabilities: ['Imprezy lokalne', 'Atrakcje turystyczne', 'Pogoda', 'Miejsca w gminie'],
    image: '/agents/przewodnik.png',
    video: '/agents/przewodnik.mp4',
    icon: <Map size={22} />,
    color: 'from-emerald-500 to-teal-700',
  },
  {
    id: 'organizator',
    label: 'Organizator',
    desc: 'Śmieci i usługi',
    about: 'Zna pełny harmonogram odbioru odpadów w każdej miejscowości gminy Rybno na 2026 rok.',
    capabilities: ['Harmonogram śmieci', 'Segregacja odpadów', 'Punkty PSZOK', 'Usługi komunalne'],
    image: '/agents/organizator.jpeg',
    video: '/agents/organizator.mp4',
    icon: <CalendarDays size={22} />,
    color: 'from-purple-500 to-fuchsia-700',
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
    color: 'from-cyan-500 to-blue-700',
  },
];

const AssistantPage: React.FC<AssistantPageProps> = ({ initialQuery, onNavigate, onInitialQuerySent }) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [chatKey, setChatKey] = useState(0);

  const activeAgent = AGENTS.find(a => a.id === selectedAgentId) ?? AGENTS[0];

  const handleSelectAgent = (id: string | null) => {
    setSelectedAgentId(id);
  };

  return (
    <div className="w-full pb-24">
      <ChatInterface
        key={chatKey}
        initialQuery={initialQuery}
        onNavigate={onNavigate}
        onInitialQuerySent={onInitialQuerySent}
        selectedAgent={selectedAgentId}
        activeAgentColor={activeAgent.color}
        headerContent={
            <div className="flex-shrink-0 w-full bg-transparent">
        {/* ZDJĘCIE AGENTA */}
        <div className="max-w-7xl mx-auto w-full px-4 md:px-8 pt-6 pb-0">
          <div className="relative w-full h-[260px] sm:h-[340px] md:h-[420px] lg:h-[480px] rounded-2xl overflow-hidden">
              {activeAgent.video ? (
                <video
                  key={activeAgent.video}
                  src={activeAgent.video}
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="w-full h-full"
                  style={{ objectFit: 'cover', objectPosition: 'center 20%', display: 'block' }}
                />
              ) : activeAgent.image ? (
                <img
                  src={activeAgent.image}
                  alt={activeAgent.label}
                  className="w-full h-full"
                  style={{ objectFit: 'cover', objectPosition: 'center 20%', display: 'block' }}
                />
              ) : (
                <div className={`w-full h-full bg-gradient-to-br ${activeAgent.color} flex items-center justify-center`}>
                  <div className="opacity-25">
                    {React.cloneElement(activeAgent.icon as React.ReactElement, { size: 64 })}
                  </div>
                </div>
              )}

              {/* Cienki gradient przy dole dla tekstów */}
              <div
                className="absolute bottom-0 left-0 right-0 pointer-events-none"
                style={{ height: '40%', background: 'linear-gradient(to top, rgba(0,0,0,0.6) 0%, transparent 100%)' }}
              />

              {/* Online badge */}
              <div className="absolute bottom-4 left-4 flex items-center gap-1.5 z-10">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-400" />
                </span>
                <span className="text-emerald-400 text-[10px] font-bold uppercase tracking-widest">Online</span>
              </div>

              {/* "Powered by OpenAI" */}
              <div
                className="absolute top-4 right-0 flex items-center justify-center px-1.5 py-3 rounded-l-lg border-l border-t border-b border-white/15 z-10"
                style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(10px)', writingMode: 'vertical-rl' }}
              >
                <span className="text-[8px] text-white/50 font-semibold tracking-widest uppercase">
                  Powered by OpenAI
                </span>
              </div>
          </div>
        </div>

        {/* PERMANENTNE INFO AGENTA */}
        <div className="max-w-7xl mx-auto w-full px-4 md:px-8 pt-3 pb-2">
          <div
            className="rounded-xl px-4 py-3.5 relative overflow-hidden"
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
            }}
          >
            {/* Opcjonalny subtelny glow z użyciem koloru agenta */}
            <div 
              className={`absolute -top-10 -right-10 w-32 h-32 rounded-full opacity-10 bg-gradient-to-br ${activeAgent.color} blur-[30px] pointer-events-none`} 
            />

            <div className="flex items-start justify-between gap-3 mb-2.5 relative z-10">
              <div>
                <p className="text-white text-[15px] font-medium flex items-center gap-2">
                  {activeAgent.label}
                </p>
                <p className="text-neutral-400 text-[13px] mt-1 leading-relaxed pr-6 max-w-2xl">
                  {activeAgent.about}
                </p>
              </div>
              <button
                onClick={() => setChatKey(k => k + 1)}
                className="text-neutral-500 hover:text-white transition-colors shrink-0 p-1.5 bg-white/5 hover:bg-white/10 rounded-full border border-white/5 hover:border-white/10 absolute top-0 right-0"
                title="Odśwież czat"
              >
                <RotateCcw size={13} />
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5 relative z-10">
              {activeAgent.capabilities.map((cap, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-medium text-neutral-300"
                  style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}
                >
                  <ChevronRight size={10} className="text-blue-400/80" />
                  {cap}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* AGENT PICKER */}
        <div className="px-1 pt-1 pb-4">
          <div className="flex gap-4 sm:justify-center overflow-x-auto scrollbar-hide px-3 py-2 mask-linear">
            {AGENTS.map(agent => {
              const isActive = selectedAgentId === agent.id;

              return (
                <button
                  key={String(agent.id)}
                  onClick={() => handleSelectAgent(agent.id)}
                  className="flex-shrink-0 flex flex-col items-center gap-2 transition-all duration-300 group focus:outline-none"
                  style={{ opacity: isActive ? 1 : 0.45 }}
                >
                  <div
                    className="relative transition-transform duration-300 group-hover:scale-105"
                    style={{
                      width: 60,
                      height: 60,
                    }}
                  >
                    {/* Kontener miniatury */}
                    <div className="w-full h-full rounded-full overflow-hidden p-[2px] relative z-10 bg-transparent">
                      {agent.image ? (
                        <img
                          src={agent.image}
                          alt={agent.label}
                          className="w-full h-full rounded-full"
                          style={{ objectFit: 'cover', objectPosition: 'center 20%' }}
                        />
                      ) : (
                        <div className={`w-full h-full rounded-full bg-gradient-to-br ${agent.color} flex items-center justify-center text-white`}>
                          {React.cloneElement(agent.icon as React.ReactElement, { size: 24 })}
                        </div>
                      )}
                    </div>

                    {/* Aktywny obrys oraz efekt "obwoluty" na hover, wzorowany na frontendzie */}
                    <div 
                      className={`absolute inset-0 rounded-full transition-all duration-300 pointer-events-none z-20 border-2 ${
                        isActive 
                        ? 'border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.6)]' 
                        : 'border-white/10 group-hover:border-blue-400/60 group-hover:shadow-[0_0_12px_rgba(96,165,250,0.3)]'
                      }`}
                    />
                  </div>
                  <span
                    className="text-[11px] font-medium whitespace-nowrap transition-colors duration-300"
                    style={{ color: isActive ? 'rgb(96,165,250)' : 'rgb(120,120,120)' }}
                  >
                    {agent.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
            </div>
          }
        />
    </div>
  );
};

export default AssistantPage;
