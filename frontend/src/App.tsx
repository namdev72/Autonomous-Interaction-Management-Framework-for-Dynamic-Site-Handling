import { QueryInput } from './components/QueryInput';
import { ActivityLog } from './components/ActivityLog';
import { AgentStatusDisplay } from './components/AgentStatusDisplay';
import { ResultPanel } from './components/ResultPanel';
import { useAgent } from './hooks/useAgent';
import { ClarificationPanel } from './components/ClarificationPanel';
import { Bot } from 'lucide-react';

function App() {
  const { status, events, result, clarification, startAgent, respondToAgent, stopAgent, clear } = useAgent();

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col p-4 md:p-8">
      <header className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600/20 text-blue-500 rounded-lg">
            <Bot size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">PRISM Agent</h1>
            <p className="text-sm text-slate-400">Autonomous Web Interaction Framework</p>
          </div>
        </div>
        
        <AgentStatusDisplay status={status} />
      </header>

      <main className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-8 min-h-0">
        
        {/* Left Column: Input and Results */}
        <div className="flex flex-col gap-8 h-full">
          <QueryInput 
            onRun={startAgent} 
            onStop={stopAgent} 
            onClear={clear} 
            status={status} 
          />

          {clarification && (
            <ClarificationPanel
              question={clarification.question}
              options={clarification.options}
              onSubmit={respondToAgent}
            />
          )}
          
          <ResultPanel result={result} />
        </div>

        {/* Right Column: Real-time Activity Log */}
        <div className="h-full min-h-[600px] flex flex-col">
          <ActivityLog events={events} />
        </div>
        
      </main>
    </div>
  );
}

export default App;
