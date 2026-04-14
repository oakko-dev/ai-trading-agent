"use client";

import { useEffect, useState, useCallback } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageInstructions } from "@/components/layout/PageInstructions";
import api from "@/lib/api";

// ─── Types ──────────────────────────────────────────────────────────────────

interface ToolInfo { name: string; description: string; }
interface IntegrationConfig {
  id: string; name: string; description: string; status: string;
  config: Record<string, string>; tools: ToolInfo[];
}
interface TestResult { name: string; status: string; latency_ms: number; detail: string; }

// ─── SVG Logos ───────────────────────────────────────────────────────────────

function TelegramLogo() {
  return (
    <svg className="size-7" viewBox="0 0 512 512"><defs><linearGradient id="tg" x1="256" y1="3.84" x2="256" y2="512" gradientUnits="userSpaceOnUse"><stop offset="0" stopColor="#2AABEE"/><stop offset="1" stopColor="#229ED9"/></linearGradient></defs><circle fill="url(#tg)" cx="256" cy="256" r="256"/><path fill="#fff" d="M115.88 253.3c74.63-32.52 124.39-53.95 149.29-64.31 71.1-29.57 85.87-34.71 95.5-34.88 2.12-.03 6.85.49 9.92 2.98 2.59 2.1 3.3 4.94 3.64 6.93.34 2 .77 6.53.43 10.08-3.85 40.48-20.52 138.71-29 184.05-3.59 19.19-10.66 25.62-17.5 26.25-14.86 1.37-26.15-9.83-40.55-19.27-22.53-14.76-35.26-23.96-57.13-38.37-25.28-16.66-8.89-25.81 5.51-40.77 3.77-3.92 69.27-63.5 70.54-68.9.16-.68.31-3.2-1.19-4.53s-3.71-.87-5.3-.51c-2.26.51-38.25 24.3-107.98 71.37-10.22 7.02-19.48 10.43-27.77 10.26-9.14-.2-26.72-5.17-39.79-9.42-16.03-5.21-28.77-7.97-27.66-16.82.57-4.61 6.92-9.32 19.04-14.14z"/></svg>
  );
}

function MT5Logo() {
  return (
    <svg className="size-7" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2">
      <path d="M3 3v18h18" strokeLinecap="round"/><path d="M7 14l4-4 3 3 7-7" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function MoonshotLogo() {
  return (
    <svg className="size-7" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M12 3a9 9 0 109 9c0-4.97-4.03-9-9-9zm0 2a7 7 0 017 7h-7V5z"
        fill="#8b5cf6"
        fillRule="evenodd"
      />
    </svg>
  );
}

const LOGOS: Record<string, () => React.ReactElement> = {
  mt5: MT5Logo,
  telegram: TelegramLogo,
  moonshot: MoonshotLogo,
};

// ─── Page ───────────────────────────────────────────────────────────────────

export default function IntegrationPage() {
  const [integrations, setIntegrations] = useState<IntegrationConfig[]>([]);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState<string | null>(null);
  const [modalId, setModalId] = useState<string | null>(null);
  const [showTools, setShowTools] = useState(false);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await api.get("/api/integration/config");
      setIntegrations(res.data.integrations);
    } catch { /* handled */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const testService = async (id: string) => {
    setTesting(id);
    try {
      const res = await api.get(`/api/integration/test/${id}`);
      setTestResults((prev) => ({ ...prev, [id]: res.data }));
    } catch {
      setTestResults((prev) => ({ ...prev, [id]: { name: id, status: "error", latency_ms: 0, detail: "Failed" } }));
    } finally { setTesting(null); }
  };

  const testAll = async () => {
    setTesting("all");
    try {
      const res = await api.get("/api/integration/status");
      const results: Record<string, TestResult> = {};
      const keyMap: Record<string, string> = {
        "MT5 Bridge": "mt5",
        "Telegram": "telegram",
        "Kimi (Moonshot)": "moonshot",
      };
      for (const s of res.data.services) results[keyMap[s.name] || s.name] = s;
      setTestResults(results);
    } catch { /* handled */ } finally { setTesting(null); }
  };

  const openModal = (id: string) => {
    setModalId(id);
    setShowTools(false);
    setEditValues({});
  };

  const handleSave = async () => {
    if (!modalId) return;
    const nonEmpty = Object.fromEntries(Object.entries(editValues).filter(([, v]) => v.trim()));
    if (Object.keys(nonEmpty).length === 0) return;
    setSaving(true);
    try {
      await api.put("/api/integration/config", { integration_id: modalId, config: nonEmpty });
      setEditValues({});
      await fetchConfig();
    } catch { /* handled */ } finally { setSaving(false); }
  };

  const modalIntg = integrations.find((i) => i.id === modalId);
  const modalResult = modalId ? testResults[modalId] : null;
  const hasEdits = Object.values(editValues).some((v) => v.trim());

  return (
    <div className="p-4 lg:p-6 space-y-6">
      <PageHeader title="Integration" subtitle="Connect external services to enable agent capabilities">
        <button type="button" onClick={testAll} disabled={testing === "all"}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {testing === "all" ? "Testing..." : "Test All"}
        </button>
      </PageHeader>

      <PageInstructions

        items={[
          "Connect external services here. Click Configure to add API keys, then Test Connection to verify.",
          "MT5 requires a running MetaTrader 5 terminal. Kimi (Moonshot) needs MOONSHOT_API_KEY. Telegram needs a bot token from @BotFather.",
        ]}
      />

      {loading ? (
        <div className="text-center text-muted-foreground py-8">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {integrations.map((intg) => {
            const result = testResults[intg.id];
            const isTestedConnected = result?.status === "connected";
            const isConfigured = intg.status === "configured";
            const showConnected = isTestedConnected || isConfigured;
            const LogoComp = LOGOS[intg.id];
            return (
              <button key={intg.id} type="button" onClick={() => openModal(intg.id)}
                className="rounded-xl border border-border bg-card p-5 text-left hover:border-primary/40 transition-all group">
                <div className="flex items-center gap-3">
                  <div className="size-10 rounded-xl bg-muted/50 flex items-center justify-center group-hover:bg-muted transition-colors">
                    {LogoComp ? <LogoComp /> : null}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-sm">{intg.name}</h3>
                      {showConnected && (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-green-500 bg-green-500/10 border border-green-500/20 rounded-full px-2 py-0.5">
                          <span className="size-1.5 rounded-full bg-green-500" />
                          Connected
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{intg.description}</p>
                  </div>
                </div>
                <div className="flex items-center justify-between mt-4 pt-3 border-t border-border/50">
                  {!showConnected && (
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                      result?.status === "error" ? "bg-red-500/10 text-red-500" :
                      "bg-amber-500/10 text-amber-500"
                    }`}>
                      {result?.status === "error" ? "Error" : "Not configured"}
                    </span>
                  )}
                  {isTestedConnected && <span className="text-xs text-muted-foreground">{result.latency_ms}ms</span>}
                  <span className="text-xs text-muted-foreground ml-auto">{intg.tools.length} tools</span>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* ─── Modal ──────────────────────────────────────────────────── */}
      {modalIntg && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] bg-black/50 overflow-y-auto" onClick={() => setModalId(null)}>
          <div className="bg-card border border-border rounded-2xl w-full max-w-lg mx-4 mb-10 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between p-6 pb-3">
              <div className="flex items-center gap-3">
                {LOGOS[modalIntg.id] && (() => { const L = LOGOS[modalIntg.id]; return <L />; })()}
                <h2 className="text-lg font-bold">{modalIntg.name}</h2>
              </div>
              <button type="button" onClick={() => setModalId(null)} className="text-muted-foreground hover:text-foreground text-2xl leading-none px-1">&times;</button>
            </div>
            <p className="px-6 text-sm text-muted-foreground">{modalIntg.description}</p>

            {/* Config fields (editable) */}
            <div className="px-6 pt-5 space-y-4">
              {Object.entries(modalIntg.config).map(([key, maskedValue]) => {
                const isSecret = key.toLowerCase().includes("key") || key.toLowerCase().includes("token");
                return (
                  <div key={key}>
                    <label className="block text-xs font-medium text-muted-foreground mb-1">
                      {key}{isSecret && " *"}
                    </label>
                    <input
                      type={isSecret ? "password" : "text"}
                      placeholder={maskedValue || "Not set"}
                      value={editValues[key] || ""}
                      onChange={(e) => setEditValues((prev) => ({ ...prev, [key]: e.target.value }))}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary placeholder:text-muted-foreground/50"
                    />
                    {isSecret && maskedValue && !editValues[key] && (
                      <p className="text-xs text-muted-foreground mt-1">Current: {maskedValue}</p>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Test Result */}
            {modalResult && (
              <div className={`mx-6 mt-4 rounded-lg p-3 flex items-center gap-2 text-sm ${
                modalResult.status === "connected"
                  ? "bg-green-500/5 border border-green-500/20 text-green-400"
                  : "bg-red-500/5 border border-red-500/20 text-red-400"
              }`}>
                <span>{modalResult.status === "connected" ? "✓" : "✗"}</span>
                <span className="flex-1">{modalResult.detail}</span>
                {modalResult.latency_ms > 0 && <span className="text-xs text-muted-foreground">{modalResult.latency_ms}ms</span>}
              </div>
            )}

            {/* Buttons */}
            <div className="px-6 pt-4 flex gap-2">
              <button type="button" onClick={() => testService(modalIntg.id)} disabled={testing === modalIntg.id}
                className="flex-1 rounded-lg border border-border px-4 py-2.5 text-sm font-medium hover:bg-accent disabled:opacity-50">
                {testing === modalIntg.id ? "Testing..." : "Test Connection"}
              </button>
              {hasEdits && (
                <button type="button" onClick={handleSave} disabled={saving}
                  className="flex-1 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                  {saving ? "Saving..." : "Save"}
                </button>
              )}
            </div>

            {/* Tools */}
            {modalIntg.tools.length > 0 && (
              <div className="px-6 pt-5 pb-6">
                <button type="button" onClick={() => setShowTools(!showTools)}
                  className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase hover:text-foreground w-full">
                  <span>Available Tools ({modalIntg.tools.length})</span>
                  <span>{showTools ? "▴" : "▾"}</span>
                </button>
                {showTools && (
                  <div className="mt-3 space-y-2 max-h-48 overflow-y-auto">
                    {modalIntg.tools.map((t) => (
                      <div key={t.name} className="flex items-start gap-2">
                        <code className="text-xs font-mono bg-primary/10 text-primary px-1.5 py-0.5 rounded shrink-0">{t.name}</code>
                        <span className="text-xs text-muted-foreground">{t.description}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
