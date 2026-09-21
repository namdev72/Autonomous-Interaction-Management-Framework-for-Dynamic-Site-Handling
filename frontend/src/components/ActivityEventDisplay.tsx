import type { AgentEvent } from '../hooks/useAgent';
import { ArrowRight, Check, X, Info, Zap } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function ActivityEventDisplay({ event }: { event: AgentEvent }) {
  const cn = (...inputs: (string | undefined | null | false)[]) => twMerge(clsx(inputs));

  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour12: false });
    } catch {
      return '';
    }
  };

  const getEventStyle = (type: string, data: any) => {
    switch (type) {
      case 'action':
        return {
          icon: <ArrowRight className="w-4 h-4 text-blue-400 mt-1" />,
          color: 'text-blue-200',
          bg: 'bg-blue-900/10 border-blue-900/50',
          text: `Action: ${data?.action?.toUpperCase()} on ${data?.target || 'page'} -> ${data?.reasoning || ''}`
        };
      case 'extraction':
        return {
          icon: <Check className="w-4 h-4 text-green-400 mt-1" />,
          color: 'text-green-200',
          bg: 'bg-green-900/10 border-green-900/50',
          text: data?.message || `Extracted: ${data?.value}`
        };
      case 'agent_completed':
        if (data?.result && !data.result.completed) {
          return {
            icon: <X className="w-4 h-4 text-red-400 mt-1" />,
            color: 'text-red-200',
            bg: 'bg-red-900/10 border-red-900/50',
            text: data.result.extracted_data?.answer || `Agent finished without completing the task (${data.result.reason}).`,
          };
        }
        return {
          icon: <Check className="w-4 h-4 text-green-400 mt-1" />,
          color: 'text-green-200',
          bg: 'bg-green-900/10 border-green-900/50',
          text: data?.result?.extracted_data?.answer || 'Agent execution completed.',
        };
      case 'agent_started':
        return {
          icon: <Check className="w-4 h-4 text-green-400 mt-1" />,
          color: 'text-green-200',
          bg: 'bg-green-900/10 border-green-900/50',
          text: data?.message || 'Agent execution starting...',
        };
      case 'error':
        return {
          icon: <X className="w-4 h-4 text-red-400 mt-1" />,
          color: 'text-red-200',
          bg: 'bg-red-900/10 border-red-900/50',
          text: data?.message || 'An error occurred'
        };
      case 'agent_stopped':
        return {
          icon: <X className="w-4 h-4 text-yellow-400 mt-1" />,
          color: 'text-yellow-200',
          bg: 'bg-yellow-900/10 border-yellow-900/50',
          text: data?.message || 'Agent stopped.'
        };
      case 'log':
        const level = data?.level?.toLowerCase() || 'info';
        if (level === 'success') {
          return {
            icon: <Check className="w-4 h-4 text-green-400 mt-1" />,
            color: 'text-green-200',
            bg: 'bg-green-900/10 border-green-900/30',
            text: data?.message
          };
        } else if (level === 'warning') {
          return {
            icon: <Zap className="w-4 h-4 text-yellow-400 mt-1" />,
            color: 'text-yellow-200',
            bg: 'bg-yellow-900/10 border-yellow-900/30',
            text: data?.message
          };
        } else if (level === 'error') {
          return {
             icon: <X className="w-4 h-4 text-red-400 mt-1" />,
             color: 'text-red-200',
             bg: 'bg-red-900/10 border-red-900/30',
             text: data?.message
          }
        }
        return {
          icon: <Info className="w-4 h-4 text-slate-400 mt-1" />,
          color: 'text-slate-300',
          bg: 'bg-transparent border-transparent',
          text: data?.message
        };
      default:
        return {
          icon: <Info className="w-4 h-4 text-slate-400 mt-1" />,
          color: 'text-slate-300',
          bg: 'bg-transparent border-transparent',
          text: JSON.stringify(data)
        };
    }
  };

  const data = event.data || {};
  const style = getEventStyle(event.type, data);

  return (
    <div className={cn("flex gap-3 p-3 rounded-lg border", style.bg, "transition-all duration-200")}>
      <div className="flex-shrink-0 w-16 text-xs text-slate-500 font-mono pt-1">
        [{formatTime(event.timestamp)}]
      </div>
      <div className="flex-shrink-0">
        {style.icon}
      </div>
      <div className={cn("text-sm flex-1 leading-relaxed whitespace-pre-wrap font-mono", style.color)}>
        {style.text}
      </div>
    </div>
  );
}
