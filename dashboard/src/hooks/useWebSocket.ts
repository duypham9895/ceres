import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';

const WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws');

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

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const [lastEvent, setLastEvent] = useState<CrawlEvent | null>(null);
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
      const data = JSON.parse(event.data) as CrawlEvent;
      if (data.type) {
        setLastEvent(data);
      }
      if (data.type === 'job_finish' || data.type === 'job_error') {
        queryClient.invalidateQueries();
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

  return { lastEvent, isConnected };
}
