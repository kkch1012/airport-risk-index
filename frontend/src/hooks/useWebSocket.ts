import { useCallback, useEffect, useRef, useState } from 'react';

export type WSStatus = 'connecting' | 'connected' | 'disconnected';

interface UseWebSocketOptions {
  /** WebSocket URL path (e.g. "/api/v1/ws/risks") */
  url: string;
  /** 메시지 수신 콜백 */
  onMessage?: (data: unknown) => void;
  /** 자동 연결 여부 (기본 true) */
  autoConnect?: boolean;
  /** 최대 재연결 대기시간 (ms, 기본 30000) */
  maxReconnectDelay?: number;
}

/**
 * WebSocket 연결 관리 훅
 *
 * - 자동 재연결 (exponential backoff: 1s → 2s → 4s → ... → max 30s)
 * - heartbeat ping/pong
 * - 연결 상태 관리
 */
export function useWebSocket({
  url,
  onMessage,
  autoConnect = true,
  maxReconnectDelay = 30000,
}: UseWebSocketOptions) {
  const [status, setStatus] = useState<WSStatus>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const getWsUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.host}`;
    return `${host}${url}`;
  }, [url]);

  const connectRef = useRef<() => void>();

  const scheduleReconnect = useCallback(() => {
    const attempt = reconnectAttemptRef.current;
    const delay = Math.min(1000 * Math.pow(2, attempt), maxReconnectDelay);
    reconnectAttemptRef.current = attempt + 1;

    reconnectTimerRef.current = setTimeout(() => {
      connectRef.current?.();
    }, delay);
  }, [maxReconnectDelay]);

  const connect = useCallback(() => {
    // 이미 연결 중이면 무시
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    setStatus('connecting');

    try {
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        reconnectAttemptRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessageRef.current?.(data);
        } catch {
          // JSON 파싱 실패 시 무시
        }
      };

      ws.onclose = () => {
        setStatus('disconnected');
        wsRef.current = null;
        scheduleReconnect();
      };

      ws.onerror = () => {
        // onclose가 이후에 호출되므로 여기서는 별도 처리 불필요
      };
    } catch {
      setStatus('disconnected');
      scheduleReconnect();
    }
  }, [getWsUrl, scheduleReconnect]);

  connectRef.current = connect;

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    reconnectAttemptRef.current = 0;
    if (wsRef.current) {
      wsRef.current.onclose = null; // 자동 재연결 방지
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('ping');
    }
  }, []);

  // 자동 연결
  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return { status, connect, disconnect, sendPing };
}
