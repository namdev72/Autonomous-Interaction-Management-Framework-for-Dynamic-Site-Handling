import { useEffect, useRef } from 'react';
import type { AgentEvent } from '../hooks/useAgent';
import { ActivityEventDisplay } from './ActivityEventDisplay';

export function ActivityLog({ events }: { events: AgentEvent[] }) {
  const endOfLogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to bottom on new event
    endOfLogRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  return (
    <div className="flex flex-col h-full bg-slate-900 rounded-xl shadow-lg border border-slate-800 overflow-hidden flex-1">
      <div className="p-4 border-b border-slate-800 bg-slate-900/50">
        <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
          Real-time Agent Activity
        </h2>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {events.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-500 text-sm">
            No activity yet. Run the agent to see live events.
          </div>
        ) : (
          events.map((evt, idx) => (
            <ActivityEventDisplay key={idx} event={evt} />
          ))
        )}
        <div ref={endOfLogRef} />
      </div>
    </div>
  );
}
