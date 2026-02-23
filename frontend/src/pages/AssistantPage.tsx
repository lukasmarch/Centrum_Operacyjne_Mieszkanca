import React from 'react';
import ChatInterface from '../../components/ChatInterface';

interface AssistantPageProps {
  initialQuery?: string;
}

const AssistantPage: React.FC<AssistantPageProps> = ({ initialQuery }) => {
  return (
    <div className="max-w-3xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-6">
        <h1 className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-violet-400 mb-1">
          Asystent AI
        </h1>
        <p className="text-sm text-slate-500">5 wyspecjalizowanych agentów gotowych do pomocy</p>
      </div>
      <ChatInterface initialQuery={initialQuery} />
    </div>
  );
};

export default AssistantPage;
