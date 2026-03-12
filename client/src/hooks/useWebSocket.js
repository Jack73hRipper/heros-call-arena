/**
 * useWebSocket — Custom hook for managing the WebSocket connection to the server.
 * Uses a ref for the message handler to avoid reconnecting when the handler changes.
 */

import { useEffect, useRef, useCallback, useState } from 'react';

export default function useWebSocket(matchId, playerId, onMessage) {
  const wsRef = useRef(null);
  const onMessageRef = useRef(onMessage);
  const pendingQueueRef = useRef([]);
  const [wsReady, setWsReady] = useState(false);

  // Keep the ref in sync with latest callback without triggering reconnect
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (!matchId || !playerId) return;

    setWsReady(false);
    pendingQueueRef.current = [];

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${window.location.host}/ws/${matchId}/${playerId}`;

    console.log(`[WS] Connecting to ${url}`);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`[WS] Connected to match ${matchId}`);
      // Flush any messages that were queued while connecting
      const pending = pendingQueueRef.current;
      pendingQueueRef.current = [];
      for (const msg of pending) {
        console.log('[WS] Flushing queued message:', msg.type || msg);
        ws.send(JSON.stringify(msg));
      }
      setWsReady(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onMessageRef.current) onMessageRef.current(data);
      } catch (err) {
        console.error('[WS] Failed to parse message:', err);
      }
    };

    ws.onclose = () => {
      console.log(`[WS] Disconnected from match ${matchId}`);
      setWsReady(false);
    };

    ws.onerror = (err) => {
      console.error('[WS] Error:', err);
    };

    return () => {
      ws.close();
      setWsReady(false);
    };
  }, [matchId, playerId]);

  const sendAction = useCallback((action) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(action));
    } else {
      // Queue messages sent while WS is still connecting
      console.log('[WS] Queuing message (WS not open yet):', action.type || action);
      pendingQueueRef.current.push(action);
    }
  }, []);

  return { sendAction, wsReady };
}
