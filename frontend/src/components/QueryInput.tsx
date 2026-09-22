import { useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { ArrowUp, Loader2 } from 'lucide-react';
import type { AgentStatus } from '../hooks/useAgent';

const EXAMPLES = [
  'Compare the price of Samsung Galaxy S25 across Amazon India and Flipkart',
  'Find the cheapest one-way flight from Delhi to Mumbai on 15 October on Google Flights',
  'Find the price of a Kindle Paperwhite on Amazon',
  'Compare boAt Airdopes 141 prices on Flipkart and Amazon India with at least 4 star rating',
];

interface QueryInputProps {
  onRun: (query: string) => void;
  onClear: () => void;
  status: AgentStatus;
  showExamples: boolean;
}

export function QueryInput({ onRun, onClear, status, showExamples }: QueryInputProps) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // A session waiting for a clarification is still live; starting another
  // run would orphan it.
  const busy = status === 'RUNNING' || status === 'WAITING_FOR_USER';
  const finished = status !== 'IDLE' && !busy;

  const handleRun = () => {
    if (query.trim() && !busy) {
      onRun(query.trim());
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleRun();
    }
  };

  const handleClear = () => {
    setQuery('');
    onClear();
    inputRef.current?.focus();
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-line bg-surface shadow-sm transition-colors focus-within:border-accent">
        <label htmlFor="query" className="sr-only">Your request</label>
        <textarea
          id="query"
          ref={inputRef}
          rows={2}
          autoFocus
          className="block max-h-60 min-h-[4.5rem] w-full resize-none bg-transparent px-5 pt-4 text-lg [field-sizing:content] leading-relaxed text-ink outline-none placeholder:text-faint disabled:text-muted"
          placeholder="e.g. Compare the price of iPhone 16 across Amazon India and Flipkart"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={busy}
        />
        <div className="flex items-center justify-between gap-3 px-3 pb-3 pl-5">
          <span className="hidden text-sm text-faint sm:inline">
            Enter to search · Shift+Enter for a new line
          </span>
          <div className="ml-auto flex items-center gap-2">
            {finished && (
              <button
                type="button"
                onClick={handleClear}
                className="rounded-lg px-3 py-2 text-sm font-medium text-muted hover:bg-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
              >
                Clear
              </button>
            )}
            <button
              type="button"
              onClick={handleRun}
              disabled={busy || !query.trim()}
              className="flex items-center gap-2 rounded-xl bg-accent px-4 py-2 font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {status === 'RUNNING' ? <Loader2 size={18} className="animate-spin" /> : <ArrowUp size={18} />}
              {status === 'RUNNING' ? 'Searching' : 'Search'}
            </button>
          </div>
        </div>
      </div>

      {showExamples && (
        <div className="flex flex-col gap-2">
          <span className="text-sm text-muted">Try one of these</span>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => {
                  setQuery(example);
                  inputRef.current?.focus();
                }}
                className="rounded-full border border-line bg-surface px-3.5 py-1.5 text-left text-sm text-muted transition-colors hover:border-accent hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
