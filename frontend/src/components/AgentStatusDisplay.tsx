import type { AgentStatus } from '../hooks/useAgent';
import { Loader2, CheckCircle2, XCircle, PauseCircle, PlayCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function AgentStatusDisplay({ status }: { status: AgentStatus }) {
  const cn = (...inputs: (string | undefined | null | false)[]) => twMerge(clsx(inputs));

  const statusConfig = {
    IDLE: {
      icon: PlayCircle,
      text: 'Ready to Run',
      color: 'text-slate-400',
      bg: 'bg-slate-800/50',
    },
    RUNNING: {
      icon: Loader2,
      text: 'Agent Running',
      color: 'text-blue-400',
      bg: 'bg-blue-900/20',
      spin: true,
    },
    COMPLETED: {
      icon: CheckCircle2,
      text: 'Task Completed',
      color: 'text-green-400',
      bg: 'bg-green-900/20',
    },
    FAILED: {
      icon: XCircle,
      text: 'Task Failed',
      color: 'text-red-400',
      bg: 'bg-red-900/20',
    },
    STOPPED: {
      icon: PauseCircle,
      text: 'Agent Stopped',
      color: 'text-yellow-400',
      bg: 'bg-yellow-900/20',
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={cn("flex items-center gap-3 px-4 py-3 rounded-lg border border-slate-700/50 shadow-sm", config.bg)}>
      <Icon className={cn("w-5 h-5", config.color, config.spin && "animate-spin")} />
      <span className={cn("font-medium tracking-wide", config.color)}>
        {config.text}
      </span>
    </div>
  );
}
