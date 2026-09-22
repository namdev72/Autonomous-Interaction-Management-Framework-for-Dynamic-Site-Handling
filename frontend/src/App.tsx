import { QueryInput } from './components/QueryInput';
import { ActivityLog } from './components/ActivityLog';
import { ProgressLine } from './components/ProgressLine';
import { ResultPanel } from './components/ResultPanel';
import { ClarificationPanel } from './components/ClarificationPanel';
import { useAgent } from './hooks/useAgent';
import { describeEvent } from './lib/present';

// Events that say what the agent is doing, for the progress line.
const PROGRESS_EVENTS = new Set(['agent_started', 'strategy', 'action', 'extraction', 'log']);

function App() {
  const { status, query, events, result, clarification, startAgent, respondToAgent, stopAgent, clear } = useAgent();

  const plan = events.find((event) => event.type === 'agent_started')?.data?.plan;
  const latest = [...events].reverse().find((event) => PROGRESS_EVENTS.has(event.type));
  const progress = latest ? describeEvent(latest).text : 'Reading your request';
  const error = [...events].reverse().find((event) => event.type === 'error');

  return (
    <div className="min-h-screen">
      <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-8 sm:px-6 sm:py-14">
        <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-display text-xl font-bold tracking-tight whitespace-nowrap text-ink">Web Task Agent</span>
          <span className="text-sm text-muted">Amazon · Flipkart · Google Flights</span>
        </header>

        <div className="flex flex-col gap-3">
          <h1 className="font-display text-4xl font-medium leading-[1.05] tracking-tight text-ink sm:text-5xl">
            What are you looking for?
          </h1>
          <p className="max-w-xl text-muted">
            Ask for a price, a product or a flight. The agent searches the sites for you and
            answers only from what it reads there.
          </p>
        </div>

        <QueryInput
          onRun={startAgent}
          onClear={clear}
          status={status}
          showExamples={status === 'IDLE'}
        />

        {status === 'RUNNING' && <ProgressLine message={progress} onStop={stopAgent} />}

        {clarification && (
          <ClarificationPanel
            question={clarification.question}
            options={clarification.options}
            onSubmit={respondToAgent}
            onCancel={stopAgent}
          />
        )}

        {status === 'STOPPED' && !result && (
          <p className="rounded-xl border border-line px-4 py-3 text-muted">Search stopped. Edit your request and search again.</p>
        )}

        {status === 'FAILED' && !result && (
          <p className="rounded-xl bg-danger-soft px-4 py-3 text-danger">
            {error?.data?.message ?? 'Could not reach the agent. Check that the server is running on port 8000.'}
          </p>
        )}

        <ResultPanel result={result} subject={plan?.subject} taskType={plan?.task_type} query={query} />

        {events.length > 0 && <ActivityLog events={events} />}
      </div>
    </div>
  );
}

export default App;
