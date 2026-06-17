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
const MAX_RECONNECT_ATTEMPTS = 20;

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
    // 우선순위: 명시적 VITE_WS_URL > VITE_API_URL에서 호스트 도출 > 현재 페이지 호스트
    const explicit = import.meta.env.VITE_WS_URL;
    if (explicit) return `${explicit}${url}`;

    // 프론트(Vercel)와 백엔드(Render)가 다른 호스트일 때, API 주소에서 WS 호스트를 도출.
    // VITE_API_URL 예: "https://xxx.onrender.com/api/v1" → "wss://xxx.onrender.com"
    const apiUrl = import.meta.env.VITE_API_URL;
    if (apiUrl && /^https?:\/\//.test(apiUrl)) {
      try {
        const u = new URL(apiUrl);
        const wsProto = u.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${wsProto}//${u.host}${url}`;
      } catch {
        // URL 파싱 실패 시 아래 폴백
      }
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${url}`;
  }, [url]);

  const connectRef = useRef<() => void>();

  const scheduleReconnect = useCallback(() => {
    const attempt = reconnectAttemptRef.current;
    if (attempt >= MAX_RECONNECT_ATTEMPTS) {
      setStatus('disconnected');
      return;
    }
    // Exponential backoff + jitter to prevent thundering herd
    const base = Math.min(1000 * Math.pow(2, attempt), maxReconnectDelay);
    const jitter = base * 0.3 * Math.random();
    const delay = base + jitter;
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
