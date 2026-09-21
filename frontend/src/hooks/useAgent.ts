import { useState, useRef, useCallback } from 'react';

export type AgentStatus = 'IDLE' | 'RUNNING' | 'WAITING_FOR_USER' | 'COMPLETED' | 'FAILED' | 'STOPPED';

export interface AgentEvent {
  type: string;
  timestamp: string;
  data: any;
}

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
      const res = await fetch(`http://localhost:8000/api/agent/respond/${sessionIdRef.current}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer }),
      });
      if (!res.ok) throw new Error('Failed to submit clarification');
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
      setClarification(null);
      setStatus('IDLE');
    }
  }, [status]);

  return { status, events, result, clarification, startAgent, respondToAgent, stopAgent, clear };
}
