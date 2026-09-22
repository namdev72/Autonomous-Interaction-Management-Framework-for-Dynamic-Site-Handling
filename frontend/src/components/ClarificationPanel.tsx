import { useState } from 'react';
import { ArrowRight } from 'lucide-react';

interface ClarificationPanelProps {
  question: string;
  options: string[];
  onSubmit: (answer: string) => void;
  onCancel: () => void;
}

export function ClarificationPanel({ question, options, onSubmit, onCancel }: ClarificationPanelProps) {
  const [answer, setAnswer] = useState('');

  const submit = (value: string) => {
    if (value.trim()) onSubmit(value.trim());
  };

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-accent/40 bg-accent-soft p-5 sm:p-6">
      <div>
        <span className="text-sm font-medium text-accent">One question before I start</span>
        <h2 className="mt-1 font-display text-2xl font-medium leading-snug text-ink">{question}</h2>
      </div>
      {options.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {options.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => submit(option)}
              className="flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2.5 font-medium text-ink transition-colors hover:border-accent focus-visible:outline-2 focus-visible:outline-accent"
            >
              {option}
              <ArrowRight size={16} className="text-accent" />
            </button>
          ))}
        </div>
      )}
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          submit(answer);
        }}
      >
        <label htmlFor="clarification" className="sr-only">Your answer</label>
        <input
          id="clarification"
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder={options.length > 0 ? 'Or type your answer' : 'Type your answer'}
          className="min-w-0 flex-1 rounded-xl border border-line bg-surface px-4 py-2.5 text-ink outline-none placeholder:text-faint focus:border-accent"
        />
        <button
          type="submit"
          disabled={!answer.trim()}
          className="rounded-xl bg-accent px-4 py-2.5 font-medium text-accent-ink hover:bg-accent-hover disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Answer
        </button>
      </form>
      <button
        type="button"
        onClick={onCancel}
        className="self-start text-sm text-muted underline-offset-4 hover:text-ink hover:underline"
      >
        Cancel this search
      </button>
    </section>
  );
}
