import { useState } from 'react';
import { ArrowRight, MessageCircleQuestion } from 'lucide-react';

interface ClarificationPanelProps {
  question: string;
  options: string[];
  onSubmit: (answer: string) => void;
}

export function ClarificationPanel({ question, options, onSubmit }: ClarificationPanelProps) {
  const [answer, setAnswer] = useState('');

  const submit = (value: string) => {
    if (value.trim()) onSubmit(value.trim());
  };

  return (
    <section className="flex flex-col gap-4 p-5 bg-slate-900 rounded-xl border border-amber-800/60 shadow-lg">
      <div className="flex items-start gap-3">
        <MessageCircleQuestion className="w-5 h-5 text-amber-400 mt-0.5" />
        <div>
          <h2 className="text-sm font-semibold text-amber-200">The agent needs your choice</h2>
          <p className="mt-1 text-sm text-slate-300">{question}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => submit(option)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-amber-700/60 bg-amber-950/30 text-amber-100 hover:bg-amber-900/50 transition-colors"
          >
            {option}
            <ArrowRight size={15} />
          </button>
        ))}
      </div>
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          submit(answer);
        }}
      >
        <input
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder="Type another answer"
          className="min-w-0 flex-1 px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 outline-none focus:border-amber-500"
        />
        <button
          type="submit"
          disabled={!answer.trim()}
          aria-label="Submit answer"
          className="px-3 py-2 rounded-lg bg-amber-600 text-white disabled:opacity-40 hover:bg-amber-500"
        >
          <ArrowRight size={18} />
        </button>
      </form>
    </section>
  );
}
