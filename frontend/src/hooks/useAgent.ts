import { useState, useRef, useCallback } from 'react';

export type AgentStatus = 'IDLE' | 'RUNNING' | 'WAITING_FOR_USER' | 'COMPLETED' | 'FAILED' | 'STOPPED';

export interface AgentEvent {
  type: string;
  timestamp: string;
  data: any;
}

// Backend address. Set VITE_API_URL (e.g. in frontend/.env) to run the UI
// against a backend other than this machine's.
const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const WS_URL = API_URL.replace(/^http/, 'ws');

export function useAgent() {
  const [status, setStatus] = useState<AgentStatus>('IDLE');
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [result, setResult] = useState<any>(null);
  const [clarification, setClarification] = useState<{ question: string; options: string[] } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const startAgent = useCallback(async (query: string) => {
    try {
      setStatus('RUNNING');
      setEvents([]);
      setResult(null);
      setClarification(null);

      // Start the task on the backend
      const res = await fetch(`${API_URL}/api/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      
      if (!res.ok) throw new Error('Failed to start agent');
      
      const { session_id } = await res.json();
      sessionIdRef.current = session_id;

      // Connect WebSocket
      const ws = new WebSocket(`${WS_URL}/api/agent/ws/${session_id}`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const parsedEvent: AgentEvent = JSON.parse(event.data);
        setEvents((prev) => [...prev, parsedEvent]);

        if (parsedEvent.type === 'user_input_required') {
          setStatus('WAITING_FOR_USER');
          setClarification({
            question: parsedEvent.data?.question || 'Please provide more information.',
            options: parsedEvent.data?.options || [],
          });
        }

        // Automatically handle status changes based on specific events
        if (parsedEvent.type === 'agent_completed') {
          // agent_completed means the run ended, not that it succeeded.
          setStatus(parsedEvent.data.result?.completed ? 'COMPLETED' : 'FAILED');
          setResult(parsedEvent.data.result);
        } else if (parsedEvent.type === 'error') {
          setStatus('FAILED');
        } else if (parsedEvent.type === 'agent_stopped') {
          setStatus('STOPPED');
        }
      };

      ws.onerror = () => {
        setStatus('FAILED');
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

  const respondToAgent = useCallback(async (answer: string) => {
    if (!sessionIdRef.current || !answer.trim()) return;
    setClarification(null);
    setStatus('RUNNING');
    try {
      const res = await fetch(`${API_URL}/api/agent/respond/${sessionIdRef.current}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer }),
      });
      if (!res.ok) throw new Error('Failed to submit clarification');
      // The backend answers 200 with not_waiting when the session is gone.
      const { status: responseStatus } = await res.json();
      if (responseStatus === 'not_waiting') throw new Error('Session is no longer waiting for an answer');
    } catch (err) {
      console.error(err);
      setStatus('FAILED');
    }
  }, []);

  const stopAgent = useCallback(async () => {
    if (sessionIdRef.current) {
      try {
        await fetch(`${API_URL}/api/agent/stop/${sessionIdRef.current}`, {
          method: 'POST',
        });
        setStatus('STOPPED');
        setClarification(null);
        if (wsRef.current) {
          wsRef.current.close();
        }
      } catch (err) {
        console.error("Failed to stop agent", err);
      }
    }
  }, []);

  const clear = useCallback(() => {
    if (status !== 'RUNNING' && status !== 'WAITING_FOR_USER') {
      setEvents([]);
      setResult(null);
      setClarification(null);
      setStatus('IDLE');
    }
  }, [status]);

  return { status, events, result, clarification, startAgent, respondToAgent, stopAgent, clear };
}
