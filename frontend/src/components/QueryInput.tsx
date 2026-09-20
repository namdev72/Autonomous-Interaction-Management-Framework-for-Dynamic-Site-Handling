import { useState } from 'react';
import type { KeyboardEvent } from 'react';
import { Play, Square, Trash2 } from 'lucide-react';
import type { AgentStatus } from '../hooks/useAgent';

interface QueryInputProps {
  onRun: (query: string) => void;
  onStop: () => void;
  onClear: () => void;
  status: AgentStatus;
}

export function QueryInput({ onRun, onStop, onClear, status }: QueryInputProps) {
  const [query, setQuery] = useState('');

  const handleRun = () => {
    if (query.trim() && status !== 'RUNNING') {
      onRun(query);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleRun();
    }
  };

  return (
    <div className="flex flex-col gap-4 p-6 bg-slate-900 rounded-xl shadow-lg border border-slate-800">
      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium text-slate-400 uppercase tracking-wider">
          Task Query
        </label>
        <textarea
          className="w-full h-32 p-4 bg-slate-950 text-slate-100 rounded-lg border border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none resize-none placeholder-slate-600"
          placeholder="What do you want the agent to do? e.g., 'Open Chrome and search for Samsung Galaxy S26'"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={status === 'RUNNING'}
        />
      </div>

      <div className="flex justify-between items-center">
        <div className="flex gap-2">
          {status !== 'RUNNING' ? (
            <button
              onClick={handleRun}
              disabled={!query.trim()}
              className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors"
            >
              <Play size={18} />
              Run Agent
            </button>
          ) : (
            <button
              onClick={onStop}
              className="flex items-center gap-2 px-6 py-2.5 bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg transition-colors"
            >
              <Square size={18} />
              Stop
            </button>
          )}

          <button
            onClick={onClear}
            disabled={status === 'RUNNING' || !query.trim()}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 font-medium rounded-lg transition-colors"
          >
            <Trash2 size={18} />
            Clear
          </button>
        </div>

        <div className="hidden sm:block text-sm text-slate-500">
          Press <kbd className="px-2 py-1 bg-slate-800 rounded text-slate-300">Enter</kbd> to run
        </div>
      </div>
    </div>
  );
}
