import { useEffect, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import type { AgentEvent } from '../hooks/useAgent';
import { ActivityEventDisplay } from './ActivityEventDisplay';

/** Every step the agent took, folded away under the result. */
export function ActivityLog({ events }: { events: AgentEvent[] }) {
  const [open, setOpen] = useState(false);
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    // Follow new steps inside the list, without scrolling the page.
    if (open && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [events, open]);

  return (
    <section className="border-t border-line pt-4">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
      >
        <ChevronRight size={16} className={`transition-transform ${open ? 'rotate-90' : ''}`} />
        {open ? 'Hide' : 'Show'} what the agent did ({events.length} {events.length === 1 ? 'step' : 'steps'})
      </button>
      {open && (
        <ol ref={listRef} className="mt-3 max-h-96 overflow-y-auto rounded-xl border border-line bg-surface py-2">
          {events.map((event, index) => (
            <ActivityEventDisplay key={index} event={event} />
          ))}
        </ol>
      )}
    </section>
  );
}
