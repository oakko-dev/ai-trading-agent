"use client";

import { useEffect, useRef, useCallback, useState } from "react";

/**
 * WebSocket URL reachable from the browser.
 * - Production (Docker + nginx gateway): same host:port as the page — nginx proxies /ws to FastAPI.
 *   Do NOT use :8080 from the browser when the UI is on :3000; cloud firewalls often block 8080 → "pending".
 * - Local dev: ws://localhost:8080/ws (API on 8080).
 * - NEXT_PUBLIC_WS_URL: use for a different host only (e.g. wss://api.example.com/ws). Same host + :8080 is ignored when the page is on another port.
 */
function resolveWsBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8080/ws";
  }

  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1";

  if (isLocal) {
    const port = process.env.NEXT_PUBLIC_BACKEND_PORT || "8080";
    return `${proto}//${host}:${port}/ws`;
  }

  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  if (explicit && !explicit.includes("localhost") && !explicit.includes("127.0.0.1")) {
    try {
      const u = new URL(explicit);
      const pagePort =
        window.location.port ||
        (window.location.protocol === "https:" ? "443" : "80");
      const explicitPort =
        u.port || (u.protocol === "wss:" || u.protocol === "https:" ? "443" : "80");

      if (u.hostname === window.location.hostname) {
        // Same host: never use baked :8080 when the page is on another port (e.g. nginx on :3000).
        if (explicitPort === "8080" && pagePort !== "8080") {
          return `${proto}//${window.location.host}/ws`;
        }
        if (u.host === window.location.host) {
          return explicit;
        }
        // Same hostname, different ports (e.g. env had IP:8080, page is IP:3000)
        return `${proto}//${window.location.host}/ws`;
      }
      // Different hostname only — split API / CDN (e.g. wss://api.example.com/ws)
      return explicit;
    } catch {
      // invalid URL — fall through
    }
  }

  return `${proto}//${window.location.host}/ws`;
}

type WSMessage = {
  channel: string;
  data: unknown;
};

type UseWebSocketReturn = {
  isConnected: boolean;
  lastMessage: WSMessage | null;
  subscribe: (channel: string, callback: (data: unknown) => void) => void;
  unsubscribe: (channel: string) => void;
};

export function useWebSocket(): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const subscribersRef = useRef<Map<string, (data: unknown) => void>>(
    new Map()
  );
  const reconnectAttemptsRef = useRef(0);
  const skipBackoffReconnectRef = useRef(false);

  const connect = useCallback(() => {
    // Don't create duplicate connections
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    const baseWsUrl = resolveWsBaseUrl();
    const token = typeof window !== "undefined" ? localStorage.getItem("token") || "" : "";
    const wsUrl = token
      ? `${baseWsUrl}?token=${encodeURIComponent(token)}`
      : baseWsUrl;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          setLastMessage(msg);

          const callback = subscribersRef.current.get(msg.channel);
          if (callback) {
            callback(msg.data);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (skipBackoffReconnectRef.current) {
          skipBackoffReconnectRef.current = false;
          return;
        }
        // Always retry with backoff (cap at 30s)
        const delay = Math.min(
          1000 * 2 ** reconnectAttemptsRef.current,
          30000
        );
        reconnectAttemptsRef.current++;
        setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // connection failed
    }
  }, []);

  useEffect(() => {
    const onTokenChanged = () => {
      reconnectAttemptsRef.current = 0;
      skipBackoffReconnectRef.current = true;
      wsRef.current?.close();
      wsRef.current = null;
      setTimeout(() => connect(), 0);
    };
    window.addEventListener("goldbot:token-changed", onTokenChanged);
    return () => window.removeEventListener("goldbot:token-changed", onTokenChanged);
  }, [connect]);

  useEffect(() => {
    connect();

    // Reconnect when tab becomes visible again (after sleep/tab switch)
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        reconnectAttemptsRef.current = 0;
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          connect();
        }
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      wsRef.current?.close();
    };
  }, [connect]);

  const subscribe = useCallback(
    (channel: string, callback: (data: unknown) => void) => {
      subscribersRef.current.set(channel, callback);
    },
    []
  );

  const unsubscribe = useCallback((channel: string) => {
    subscribersRef.current.delete(channel);
  }, []);

  return { isConnected, lastMessage, subscribe, unsubscribe };
}
