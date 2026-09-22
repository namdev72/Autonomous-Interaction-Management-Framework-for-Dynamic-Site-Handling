import type { AgentEvent } from '../hooks/useAgent';
import { describeEvent } from '../lib/present';
import type { Tone } from '../lib/present';

const DOT: Record<Tone, string> = {
  plain: 'bg-faint',
  good: 'bg-accent',
  warn: 'bg-deal-bar',
  bad: 'bg-danger',
  ask: 'bg-deal',
};

function formatTime(isoString: string) {
  const date = new Date(isoString);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString([], { hour12: false });
}

export function ActivityEventDisplay({ event }: { event: AgentEvent }) {
  const { text, detail, tone } = describeEvent(event);
  return (
    <li className="flex gap-3 px-4 py-1.5 text-sm">
      <span className="w-16 shrink-0 pt-0.5 font-mono text-xs text-faint">{formatTime(event.timestamp)}</span>
      <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${DOT[tone]}`} />
      <div className="min-w-0 flex-1">
        <p className={`break-words ${tone === 'bad' ? 'text-danger' : 'text-ink'}`}>{text}</p>
        {detail && <p className="break-words text-muted">{detail}</p>}
      </div>
    </li>
  );
}
