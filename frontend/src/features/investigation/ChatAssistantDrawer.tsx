import React, { useState, useEffect, useRef } from "react";
import {
  MessageSquareCode,
  Send,
  X,
  Sparkles,
  Database,
  Code2,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Trash2,
  Layers,
} from "lucide-react";
import { sendInvestigationChat } from "../../api/client";
import type {
  ChatMessage,
  ChatInvestigationResponse,
  EvidenceReference,
} from "../../types/investigation";

interface ChatAssistantDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  repoId?: string;
  graphName?: string;
  commitSha?: string;
  selectedEntityId?: string;
  onNavigateToTab?: (tab: string, entityId?: string) => void;
}

function getCurrentTimestamp(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export const ChatAssistantDrawer: React.FC<ChatAssistantDrawerProps> = ({
  isOpen,
  onClose,
  repoId,
  graphName,
  commitSha,
  selectedEntityId,
  onNavigateToTab,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuestion, setInputQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatInvestigationResponse | null>(null);
  const [conversationId, setConversationId] = useState<string>(() => `conv_${Date.now()}`);
  const [expandedTraceIdx, setExpandedTraceIdx] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [prevRepo, setPrevRepo] = useState(repoId);

  if (repoId !== prevRepo) {
    setPrevRepo(repoId);
    if (messages.length > 0) {
      setMessages([]);
      setLastResponse(null);
    }
  }

  // Auto-scroll to bottom of chat
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (questionText?: string) => {
    const q = (questionText || inputQuestion).trim();
    if (!q || isLoading) return;

    setInputQuestion("");
    const userMsg: ChatMessage = {
      role: "user",
      content: q,
      timestamp: getCurrentTimestamp(),
    };

    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setIsLoading(true);

    try {
      const resp = await sendInvestigationChat({
        question: q,
        repo_id: repoId || "repo:local_nexusact",
        graph_name: graphName || "nexusact_main",
        conversation_id: conversationId || undefined,
        history: newHistory,
        target_entity_id: selectedEntityId,
        commit_sha: commitSha,
      });

      setLastResponse(resp);
      if (resp.conversation_id) {
        setConversationId(resp.conversation_id);
      }

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: resp.answer,
        timestamp: getCurrentTimestamp(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        role: "assistant",
        content: `**Investigation Failed:** ${err.message || "Could not query FalkorDB or generate answer."}`,
        timestamp: getCurrentTimestamp(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearHistory = () => {
    setMessages([]);
    setLastResponse(null);
    setConversationId(`conv_${Date.now()}`);
  };

  const handleEvidenceClick = (ev: EvidenceReference) => {
    if (!onNavigateToTab) return;
    const pTarget = ev.panel_target || "graph";
    onNavigateToTab(pTarget, ev.entity_id);
  };

  useEffect(() => {
    if (!isOpen) return;
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const currentProvider = lastResponse?.provider_status;
  const modelTitle =
    currentProvider === "gemini"
      ? `${lastResponse?.model_name || "Gemini"} (Live AI)`
      : currentProvider === "fallback"
      ? "Deterministic Cypher Grounding (Fallback)"
      : "FalkorDB Read-Only Cypher Engine";

  return (
    <div
      role="dialog"
      aria-label="NexusAct Graph Assistant Drawer"
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: "420px",
        maxWidth: "92vw",
        height: "100vh",
        maxHeight: "100vh",
        boxSizing: "border-box",
        backgroundColor: "var(--bg-card, #ffffff)",
        borderLeft: "1px solid var(--border-subtle, #e2e8f0)",
        boxShadow: "-4px 0 24px rgba(0, 0, 0, 0.12)",
        display: "flex",
        flexDirection: "column",
        zIndex: 1000,
        animation: "slideInRight 0.2s ease-out",
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          padding: "0.85rem 1rem",
          backgroundColor: "var(--bg-muted, #f8fafc)",
          borderBottom: "1px solid var(--border-subtle, #e2e8f0)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "6px",
              backgroundColor: "var(--accent-blue-subtle, #eff6ff)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Sparkles size={16} color="var(--accent-blue, #2563eb)" />
          </div>
          <div>
            <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-primary, #0f172a)" }}>
              NexusAct Graph Assistant
            </div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted, #64748b)", display: "flex", gap: "0.35rem", alignItems: "center" }}>
              <span>{graphName || "nexusact_main"}</span>
              <span>•</span>
              <span style={{ color: currentProvider === "gemini" ? "#16a34a" : "#d97706", fontWeight: 600 }}>
                {modelTitle}
              </span>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
          {messages.length > 0 && (
            <button
              onClick={handleClearHistory}
              title="Clear conversation"
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: "0.35rem",
                borderRadius: "4px",
                color: "var(--text-muted, #64748b)",
              }}
            >
              <Trash2 size={15} />
            </button>
          )}
          <button
            onClick={onClose}
            title="Close Assistant"
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: "0.35rem",
              borderRadius: "4px",
              color: "var(--text-secondary, #334155)",
            }}
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* ── Active Context Bar ── */}
      <div
        style={{
          padding: "0.45rem 1rem",
          backgroundColor: "#f1f5f9",
          borderBottom: "1px solid var(--border-subtle, #e2e8f0)",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          fontSize: "0.72rem",
          color: "var(--text-secondary, #475569)",
        }}
      >
        <Database size={13} color="var(--accent-blue, #2563eb)" />
        <span style={{ fontWeight: 600 }}>Source:</span>
        <span style={{ fontFamily: "var(--font-mono, monospace)", maxWidth: "160px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {repoId || "nexusact_local"}
        </span>
        {commitSha && (
          <span style={{ color: "var(--text-muted, #64748b)" }}>
            ({commitSha.slice(0, 7)})
          </span>
        )}
      </div>

      {/* ── Message Thread ── */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "1rem",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
          backgroundColor: "var(--bg-app, #f8fafc)",
        }}
      >
        {messages.length === 0 ? (
          <div style={{ textAlign: "center", padding: "2rem 1rem", color: "var(--text-muted, #64748b)" }}>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "10px",
                backgroundColor: "var(--accent-blue-subtle, #eff6ff)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 0.75rem",
              }}
            >
              <MessageSquareCode size={22} color="var(--accent-blue, #2563eb)" />
            </div>
            <h4 style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-primary, #0f172a)", marginBottom: "0.35rem" }}>
              Graph-Grounded Source Chat
            </h4>
            <p style={{ fontSize: "0.78rem", lineHeight: 1.4, marginBottom: "1.25rem" }}>
              Ask anything about the active repository or financial dataset. NexusAct executes real read-only Cypher in FalkorDB and explains the findings.
            </p>

            <div style={{ textAlign: "left", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <div style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted, #64748b)" }}>
                Suggested Questions:
              </div>
              {[
                "Which modules have the highest architectural centrality?",
                "What would break if the core router module is removed?",
                "Who are the top contributors and qualified reviewers?",
                "Find the shortest dependency path between endpoints and database client",
              ].map((starter, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(starter)}
                  style={{
                    textAlign: "left",
                    padding: "0.5rem 0.65rem",
                    fontSize: "0.75rem",
                    backgroundColor: "#ffffff",
                    border: "1px solid var(--border-subtle, #e2e8f0)",
                    borderRadius: "6px",
                    cursor: "pointer",
                    color: "var(--text-primary, #1e293b)",
                    transition: "all 0.15s ease",
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.borderColor = "var(--accent-blue, #2563eb)")}
                  onMouseOut={(e) => (e.currentTarget.style.borderColor = "var(--border-subtle, #e2e8f0)")}
                >
                  {starter}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                gap: "0.25rem",
              }}
            >
              <div
                style={{
                  maxWidth: "92%",
                  padding: "0.75rem 0.9rem",
                  borderRadius: msg.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                  backgroundColor: msg.role === "user" ? "var(--accent-blue, #2563eb)" : "#ffffff",
                  color: msg.role === "user" ? "#ffffff" : "var(--text-primary, #0f172a)",
                  border: msg.role === "user" ? "none" : "1px solid var(--border-subtle, #e2e8f0)",
                  fontSize: "0.82rem",
                  lineHeight: 1.5,
                  boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                  wordBreak: "break-word",
                  whiteSpace: "pre-wrap",
                }}
              >
                {msg.content}
              </div>

              {msg.timestamp && (
                <span style={{ fontSize: "0.65rem", color: "var(--text-muted, #94a3b8)", padding: "0 0.25rem" }}>
                  {msg.timestamp}
                </span>
              )}
            </div>
          ))
        )}

        {/* Loading Indicator */}
        {isLoading && (
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", padding: "0.5rem", color: "var(--text-secondary, #475569)", fontSize: "0.78rem" }}>
            <div
              style={{
                width: "16px",
                height: "16px",
                border: "2px solid var(--accent-blue, #2563eb)",
                borderTopColor: "transparent",
                borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
              }}
            />
            <span>Executing FalkorDB Cypher & analyzing connected data...</span>
          </div>
        )}

        {/* Trace and Evidence Inspector for Last Response */}
        {lastResponse && !isLoading && (
          <div style={{ marginTop: "0.5rem", display: "flex", flexDirection: "column", gap: "0.65rem" }}>
            {/* Cypher Traces */}
            {lastResponse.query_traces && lastResponse.query_traces.length > 0 && (
              <div
                style={{
                  backgroundColor: "#ffffff",
                  border: "1px solid var(--border-subtle, #e2e8f0)",
                  borderRadius: "8px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    padding: "0.5rem 0.75rem",
                    backgroundColor: "var(--bg-muted, #f8fafc)",
                    borderBottom: "1px solid var(--border-subtle, #e2e8f0)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    color: "var(--text-primary, #0f172a)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <Code2 size={14} color="var(--accent-blue, #2563eb)" />
                    <span>FalkorDB Executed Cypher ({lastResponse.query_traces.length})</span>
                  </div>
                </div>

                {lastResponse.query_traces.map((trace, tIdx) => {
                  const isExpanded = expandedTraceIdx === tIdx;
                  return (
                    <div key={tIdx} style={{ borderBottom: tIdx < lastResponse.query_traces.length - 1 ? "1px solid #f1f5f9" : "none" }}>
                      <button
                        onClick={() => setExpandedTraceIdx(isExpanded ? null : tIdx)}
                        style={{
                          width: "100%",
                          textAlign: "left",
                          padding: "0.45rem 0.75rem",
                          background: "transparent",
                          border: "none",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          fontSize: "0.72rem",
                          color: "var(--text-secondary, #334155)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          <span style={{ fontFamily: "var(--font-mono, monospace)", color: "#0284c7" }}>
                            {trace.cypher_query.split("\n")[0].slice(0, 32)}...
                          </span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                          <span style={{ color: "#16a34a", fontWeight: 600 }}>{trace.rows_returned} rows</span>
                          <span style={{ color: "var(--text-muted, #94a3b8)" }}>{trace.execution_time_ms}ms</span>
                        </div>
                      </button>

                      {isExpanded && (
                        <div style={{ padding: "0.5rem 0.75rem", backgroundColor: "#0f172a", color: "#f8fafc", fontSize: "0.72rem", fontFamily: "var(--font-mono, monospace)", overflowX: "auto" }}>
                          <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{trace.cypher_query}</pre>
                          {trace.error_message && (
                            <div style={{ color: "#f87171", marginTop: "0.35rem" }}>
                              Error: {trace.error_message}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Evidence References */}
            {lastResponse.evidence_references && lastResponse.evidence_references.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted, #64748b)", textTransform: "uppercase" }}>
                  Verified Evidence Citations:
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                  {lastResponse.evidence_references.map((ev, eIdx) => (
                    <button
                      key={eIdx}
                      onClick={() => handleEvidenceClick(ev)}
                      title={`Jump to ${ev.entity_type} in ${ev.panel_target || "graph"}`}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.35rem",
                        padding: "0.25rem 0.5rem",
                        borderRadius: "4px",
                        backgroundColor: "#ffffff",
                        border: "1px solid var(--border-subtle, #e2e8f0)",
                        fontSize: "0.7rem",
                        cursor: "pointer",
                        color: "var(--text-primary, #0f172a)",
                      }}
                    >
                      <Layers size={12} color="var(--accent-blue, #2563eb)" />
                      <span>{ev.label}</span>
                      <ExternalLink size={10} color="var(--text-muted, #94a3b8)" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Suggested Followups */}
            {lastResponse.suggested_followups && lastResponse.suggested_followups.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", marginTop: "0.25rem" }}>
                <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted, #64748b)", textTransform: "uppercase" }}>
                  Follow-Up Questions:
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                  {lastResponse.suggested_followups.map((fol, fIdx) => (
                    <button
                      key={fIdx}
                      onClick={() => handleSend(fol)}
                      style={{
                        textAlign: "left",
                        padding: "0.4rem 0.6rem",
                        fontSize: "0.72rem",
                        backgroundColor: "#ffffff",
                        border: "1px solid var(--border-subtle, #e2e8f0)",
                        borderRadius: "6px",
                        cursor: "pointer",
                        color: "var(--text-primary, #1e293b)",
                      }}
                    >
                      {fol}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input Box ── */}
      <div
        style={{
          padding: "0.75rem 1rem",
          backgroundColor: "#ffffff",
          borderTop: "1px solid var(--border-subtle, #e2e8f0)",
          display: "flex",
          gap: "0.5rem",
          alignItems: "flex-end",
        }}
      >
        <textarea
          value={inputQuestion}
          onChange={(e) => setInputQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about dependencies, blast radius, contributors, or Cypher..."
          rows={2}
          style={{
            flex: 1,
            resize: "none",
            borderRadius: "6px",
            border: "1px solid var(--border-subtle, #cbd5e1)",
            padding: "0.5rem 0.65rem",
            fontSize: "0.8rem",
            fontFamily: "inherit",
            outline: "none",
            color: "var(--text-primary, #0f172a)",
          }}
        />

        <button
          onClick={() => handleSend()}
          disabled={!inputQuestion.trim() || isLoading}
          aria-label="Send message"
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "6px",
            backgroundColor: !inputQuestion.trim() || isLoading ? "#94a3b8" : "var(--accent-blue, #2563eb)",
            color: "#ffffff",
            border: "none",
            cursor: !inputQuestion.trim() || isLoading ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
};
