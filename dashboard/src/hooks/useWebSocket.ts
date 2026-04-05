import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';

const WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace(/^https:/, 'wss:')
  .replace(/^http:/, 'ws:');

export interface CrawlEvent {
  type: string;
  job_id: string;
  agent?: string;
  step?: string;
  step_index?: number;
  total_steps?: number;
  banks_processed?: number;
  banks_total?: number;
  banks_failed?: number;
  error?: string;
  result?: Record<string, unknown>;
}

const SESSION_KEY = 'ceres-event-buffer';

function loadEventBuffer(): CrawlEvent[] {
  try {
    const stored = sessionStorage.getItem(SESSION_KEY);
    return stored ? (JSON.parse(stored) as CrawlEvent[]) : [];
  } catch {
    return [];
  }
}

function saveEventBuffer(events: CrawlEvent[]): void {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(events));
  } catch {
    // sessionStorage unavailable — ignore
  }
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const [lastEvent, setLastEvent] = useState<CrawlEvent | null>(null);
  const [eventBuffer, setEventBuffer] = useState<CrawlEvent[]>(loadEventBuffer);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    const ws = new WebSocket(`${WS_URL}/ws/crawl-status`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      ws.send(JSON.stringify({ subscribe: 'all' }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as CrawlEvent;
        if (data.type) {
          setLastEvent(data);
          setEventBuffer((prev) => {
            const next = [data, ...prev].slice(0, 20);
            saveEventBuffer(next);
            return next;
          });
        }
        if (data.type === 'job_finish' || data.type === 'job_error') {
          queryClient.invalidateQueries();
        }
      } catch (e) {
        console.warn('WebSocket: invalid JSON received', e);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      reconnectTimer.current = setTimeout(connect, 3000);
    };
  }, [queryClient]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { lastEvent, eventBuffer, isConnected };
}
