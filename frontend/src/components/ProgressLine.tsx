import { Square } from 'lucide-react';

/** What the agent is doing right now, while a search runs. */
export function ProgressLine({ message, onStop }: { message: string; onStop: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3" role="status" aria-live="polite">
      <span className="relative flex h-2.5 w-2.5 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent" />
      </span>
      <p className="min-w-0 flex-1 truncate text-sm text-muted">{message}</p>
      <button
        type="button"
        onClick={onStop}
        className="flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-muted hover:bg-sunken hover:text-danger focus-visible:outline-2 focus-visible:outline-accent"
      >
        <Square size={14} />
        Stop
      </button>
    </div>
  );
}
