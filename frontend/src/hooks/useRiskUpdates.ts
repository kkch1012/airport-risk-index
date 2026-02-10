import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useWebSocket, type WSStatus } from './useWebSocket';

interface WSRiskUpdate {
  type: 'risk_update' | 'connected' | 'heartbeat' | 'error';
  timestamp: string;
  data?: {
    airports?: {
      airport_code: string;
      airport_name: string;
      total_score: number;
      risk_level: string;
    }[];
    summary?: {
      total_airports: number;
      high_risk_count: number;
      average_score: number;
    };
    channel?: string;
    message?: string;
  };
}

interface UseRiskUpdatesOptions {
  /** 특정 공항 코드 (없으면 전체) */
  airportCode?: string;
  /** WebSocket 활성화 여부 (기본 true) */
  enabled?: boolean;
}

/**
 * 위험지수 실시간 업데이트 훅
 *
 * - WebSocket으로 risk_update 수신 시 React Query 캐시 자동 업데이트
 * - WebSocket 연결 실패 시 기존 polling(refetchInterval) 유지
 */
export function useRiskUpdates({ airportCode, enabled = true }: UseRiskUpdatesOptions = {}): {
  wsStatus: WSStatus;
} {
  const queryClient = useQueryClient();

  const handleMessage = useCallback(
    (raw: unknown) => {
      if (typeof raw !== 'object' || raw === null || !('type' in raw)) return;
      const msg = raw as WSRiskUpdate;

      if (msg.type === 'risk_update' && msg.data?.airports) {
        // 대시보드 캐시 무효화 → refetch
        queryClient.invalidateQueries({ queryKey: ['dashboard'] });

        // 특정 공항 캐시도 무효화
        if (airportCode) {
          queryClient.invalidateQueries({
            queryKey: ['airportRisk', airportCode],
          });
        } else {
          // 전체 모드: 모든 공항 캐시 무효화
          for (const airport of msg.data.airports) {
            queryClient.invalidateQueries({
              queryKey: ['airportRisk', airport.airport_code],
            });
          }
        }
      }
    },
    [queryClient, airportCode],
  );

  const wsUrl = airportCode
    ? `/api/v1/ws/risks/${airportCode}`
    : '/api/v1/ws/risks';

  const { status } = useWebSocket({
    url: wsUrl,
    onMessage: handleMessage,
    autoConnect: enabled,
  });

  return { wsStatus: status };
}
