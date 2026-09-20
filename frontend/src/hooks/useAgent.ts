import { useState, useRef, useCallback } from 'react';

export type AgentStatus = 'IDLE' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'STOPPED';

export interface AgentEvent {
  type: string;
  timestamp: string;
  data: any;
}

export function useAgent() {
  const [status, setStatus] = useState<AgentStatus>('IDLE');
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [result, setResult] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const startAgent = useCallback(async (query: string) => {
    try {
      setStatus('RUNNING');
      setEvents([]);
      setResult(null);

      // Start the task on the backend
      const res = await fetch('http://localhost:8000/api/agent/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      
      if (!res.ok) throw new Error('Failed to start agent');
      
      const { session_id } = await res.json();
      sessionIdRef.current = session_id;

      // Connect WebSocket
      const ws = new WebSocket(`ws://localhost:8000/api/agent/ws/${session_id}`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const parsedEvent: AgentEvent = JSON.parse(event.data);
        setEvents((prev) => [...prev, parsedEvent]);

        // Automatically handle status changes based on specific events
        if (parsedEvent.type === 'agent_completed') {
          setStatus('COMPLETED');
          setResult(parsedEvent.data.result);
        } else if (parsedEvent.type === 'error') {
          setStatus('FAILED');
        } else if (parsedEvent.type === 'agent_stopped') {
          setStatus('STOPPED');
        }
      };

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
      };

    } catch (err) {
      console.error(err);
      setStatus('FAILED');
    }
  }, []);

  const stopAgent = useCallback(async () => {
    if (sessionIdRef.current) {
      try {
        await fetch(`http://localhost:8000/api/agent/stop/${sessionIdRef.current}`, {
          method: 'POST',
        });
        setStatus('STOPPED');
        if (wsRef.current) {
          wsRef.current.close();
        }
      } catch (err) {
        console.error("Failed to stop agent", err);
      }
    }
  }, []);

  const clear = useCallback(() => {
    if (status !== 'RUNNING') {
      setEvents([]);
      setResult(null);
      setStatus('IDLE');
    }
  }, [status]);

  return { status, events, result, startAgent, stopAgent, clear };
}
