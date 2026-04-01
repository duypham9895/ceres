import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

const WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws');

export interface CrawlEvent {
  event: string;
  job_id: string;
  agent?: string;
  message?: string;
  status?: string;
  error?: string;
  result?: Record<string, unknown>;
  ts: string;
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const [lastEvent, setLastEvent] = useState<CrawlEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/crawl-status`);
    wsRef.current = ws;
    ws.onopen = () => {
      setIsConnected(true);
      ws.send(JSON.stringify({ subscribe: 'all' }));
    };
    ws.onmessage = (event) => {
      const data: CrawlEvent = JSON.parse(event.data);
      setLastEvent(data);
      if (data.event === 'crawl_finished' || data.event === 'crawl_error') {
        queryClient.invalidateQueries();
      }
    };
    ws.onclose = () => setIsConnected(false);
    return () => ws.close();
  }, [queryClient]);

  return { lastEvent, isConnected };
}
