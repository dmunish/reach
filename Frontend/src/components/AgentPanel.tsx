import React, { useState, useRef, useEffect, useCallback } from "react";
import { supabase } from "../lib/supabase";
import { Session } from "@supabase/supabase-js";
import { LoginPage } from "./LoginPage";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import EChartsReact from "echarts-for-react";

export interface AgentPanelProps {
  isVisible: boolean;
  onClose: () => void;
  onMapFlyTo?: (lng: number, lat: number, zoom?: number) => void;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  toolCalls?: any[];
  uiAction?: {
    action: string;
    config?: any;
    dataset?: any;
    description?: string;
    coordinates?: [number, number];
    zoom?: number;
    payload?: {
      coordinates?: [number, number];
      zoom?: number;
      [key: string]: any;
    };
    [key: string]: any;
  };
}

export const AgentPanel: React.FC<AgentPanelProps> = ({
  isVisible,
  onClose,
  onMapFlyTo,
}) => {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [showLoginPage, setShowLoginPage] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load session on mount
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
      if (!session) {
        setShowLoginPage(true);
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (session) {
        setShowLoginPage(false);
      } else {
        setShowLoginPage(true);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    if (isVisible) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isVisible]);

  // Auto-fit textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(
        textareaRef.current.scrollHeight,
        120
      ) + "px";
    }
  }, [inputValue]);

  const sendMessage = useCallback(async () => {
    if (!session) {
      setShowLoginPage(true);
      return;
    }

    const message = inputValue.trim();
    if (!message) return;

    // Add user message to display
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: message,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");

    try {
      setIsStreaming(true);
      const token = (await supabase.auth.getSession()).data.session?.access_token;

      if (!token) {
        setShowLoginPage(true);
        return;
      }

      // Abort previous request if still streaming
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      abortControllerRef.current = new AbortController();

      const response = await fetch(
        `${import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"}/api/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message,
            conversation_id: conversationId,
          }),
          signal: abortControllerRef.current.signal,
        }
      );

      if (!response.ok) {
        if (response.status === 403) {
          setShowLoginPage(true);
        }
        throw new Error("Failed to send message");
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      let assistantContent = "";
      let chartAction: Message["uiAction"] | undefined;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = new TextDecoder().decode(value);
        const lines = text.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.event === "chunk") {
                assistantContent += data.data.content || "";
                // Update the assistant message in real-time
                setMessages((prev) => {
                  const lastMsg = prev[prev.length - 1];
                  if (lastMsg && lastMsg.role === "assistant") {
                    return [
                      ...prev.slice(0, -1),
                      { ...lastMsg, content: assistantContent },
                    ];
                  }
                  // First chunk, add the assistant message
                  return [...prev, {
                    id: `assistant-${Date.now()}`,
                    role: "assistant",
                    content: assistantContent,
                    timestamp: Date.now(),
                  }];
                });
              } else if (data.event === "ui_action") {
                const action = data.data;
                if (
                  action.action === "render_chart" ||
                  action.action === "map_update"
                ) {
                  chartAction = action;
                  setMessages((prev) => {
                    const lastMsg = prev[prev.length - 1];
                    if (lastMsg && lastMsg.role === "assistant") {
                      return [
                        ...prev.slice(0, -1),
                        { ...lastMsg, uiAction: chartAction },
                      ];
                    }
                    return prev;
                  });
                }
              }
            } catch {
              // Skip non-JSON lines
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      console.error("Error sending message:", error);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: "Sorry, there was an error processing your request.",
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsStreaming(false);
    }
  }, [inputValue, session, conversationId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleLoginSuccess = () => {
    setShowLoginPage(false);
  };

  return (
    <div
      className={`fixed 
        bottom-4 left-4 right-4
        sm:left-22 sm:right-4
        top-20 sm:top-4
        frosted-glass 
        transform transition-all duration-300 ease-in-out z-40 
        overflow-hidden
        flex flex-col
        ${
          isVisible
            ? "translate-y-0 opacity-100"
            : "translate-y-full opacity-0 pointer-events-none"
        }
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-stone/20">
        <div className="flex items-center gap-3">
          <svg
            className="w-5 h-5 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            strokeWidth="2"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <h3 className="text-base font-medium text-white">Analytics & QA Agent</h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-bangladesh-green rounded-full transition-colors"
        >
          <svg
            className="w-4 h-4 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <div className="w-full h-px bg-stone mb-4"></div>

      {/* Content */}
      <div className="flex-1 flex flex-col min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin h-6 w-6 border-2 border-caribbean-green border-t-transparent rounded-full"></div>
          </div>
        ) : !session ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center max-w-md mx-auto py-8">
            <div className="w-16 h-16 bg-bangladesh-green/20 flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-bangladesh-green"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                />
              </svg>
            </div>
            <h4 className="text-lg font-semibold text-white mb-2">Sign In Required</h4>
            <p className="text-stone text-sm mb-6">
              Please sign in to access the Analytics & QA Agent.
            </p>
            <button
              onClick={() => setShowLoginPage(true)}
              className="px-6 py-2 bg-bangladesh-green hover:bg-mountain-meadow text-white font-medium rounded transition-colors"
            >
              Sign In
            </button>
          </div>
        ) : (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto dark-scrollbar px-6 py-4 space-y-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-stone">
                  <svg
                    className="w-12 h-12 mb-4 opacity-20"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth="2"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                    />
                  </svg>
                  <p className="text-sm">Ask me about alerts, patterns or data analysis.</p>
                </div>
              ) : (
                messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[85%] sm:max-w-[70%] rounded-lg px-4 py-3 ${
                        msg.role === "user"
                          ? "bg-bangladesh-green text-white"
                          : "bg-white/5 border border-white/10 text-gray-100"
                      }`}
                    >
                      {msg.role === "assistant" ? (
                        <div className="prose prose-invert max-w-none text-sm">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                              code: ({ inline, node, ...props }: any) => (
                                <code
                                  className={`${
                                    inline
                                      ? "bg-white/10 px-1.5 py-0.5 rounded text-xs font-mono"
                                      : "block bg-white/10 p-2 rounded mt-2 mb-2 text-xs font-mono"
                                  }`}
                                  {...props}
                                />
                              ),
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <p className="text-sm break-words">{msg.content}</p>
                      )}

                      {msg.uiAction?.action === "render_chart" && msg.uiAction?.config && (
                        <div className="mt-4 bg-white/5 rounded p-3 border border-white/10">
                          <EChartsReact
                            option={msg.uiAction.config}
                            style={{ height: "300px", width: "100%" }}
                            theme="dark"
                          />
                          {msg.uiAction.description && (
                            <p className="text-xs text-stone mt-2 italic">{msg.uiAction.description}</p>
                          )}
                        </div>
                      )}

                      {msg.uiAction?.action === "map_update" && onMapFlyTo && (
                        <div className="mt-3">
                          <button
                            onClick={() => {
                              const coords = msg.uiAction?.coordinates || msg.uiAction?.payload?.coordinates;
                              const zoom = msg.uiAction?.zoom || msg.uiAction?.payload?.zoom || 12;
                              if (coords && coords[0] && coords[1]) {
                                onMapFlyTo(coords[0], coords[1], zoom);
                              }
                            }}
                            className="text-xs flex items-center gap-2 bg-bangladesh-green/40 hover:bg-bangladesh-green/60 text-white px-3 py-1.5 rounded transition-colors"
                          >
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            Explore on Map
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-6 border-t border-white/10 bg-rich-black/40">
              <div className="max-w-4xl mx-auto flex gap-3 items-end">
                <textarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type your message..."
                  disabled={isStreaming}
                  rows={1}
                  className="flex-1 bg-white/5 border border-white/10 text-white placeholder-stone rounded px-4 py-3 text-sm resize-none focus:outline-none focus:border-caribbean-green transition-colors disabled:opacity-50"
                />
                <button
                  onClick={sendMessage}
                  disabled={isStreaming || !inputValue.trim()}
                  className="bg-bangladesh-green hover:bg-mountain-meadow disabled:opacity-50 text-white p-3 rounded transition-colors"
                >
                  {isStreaming ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {showLoginPage && (
        <div className="absolute inset-0 z-50 bg-rich-black/90 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="max-w-md mx-auto mt-12">
            <LoginPage
              isVisible={true}
              onClose={() => setShowLoginPage(false)}
              onSuccess={handleLoginSuccess}
            />
          </div>
        </div>
      )}
    </div>
  );
};
