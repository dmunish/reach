import React, { useState, useRef, useEffect, useCallback } from "react";
import { supabase } from "../lib/supabase";
import { Session } from "@supabase/supabase-js";
import { LoginPage } from "./LoginPage";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import EChartsReact from "echarts-for-react";
import "echarts-gl";
import * as echarts from "echarts";

export interface AgentPanelProps {
  isVisible: boolean;
  onClose: () => void;
  onMapUpdate?: (
    centroid?: [number, number],
    bbox?: { xmin: number; ymin: number; xmax: number; ymax: number },
    polygon?: any
  ) => void;
}

interface Message {
  id: string;
  type: "human" | "ai" | "tool";
  data: {
    content: string;
    name?: string;
    tool_calls?: any[];
    artifact?: any;
    [key: string]: any;
  };
}

interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

const TOOL_DESCRIPTIONS: Record<string, string> = {
  query: "Fetched data",
  chart: "Generated chart",
  map: "Updated map",
  examples: "Reading chart examples",
};

const ResizableChart: React.FC<{ config: string; description?: string }> = ({ config, description }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState<'right' | 'bottom' | 'corner' | null>(null);

  useEffect(() => {
    if (!isDragging) return;

    const onMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      
      if (isDragging === 'right' || isDragging === 'corner') {
        const newWidth = Math.max(300, e.clientX - rect.left);
        containerRef.current.style.width = `${newWidth}px`;
      }
      if (isDragging === 'bottom' || isDragging === 'corner') {
        const newHeight = Math.max(200, e.clientY - rect.top);
        containerRef.current.style.height = `${newHeight}px`;
      }
    };

    const onMouseUp = () => setIsDragging(null);

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    
    // Prevent text selection while dragging
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.userSelect = '';
    };
  }, [isDragging]);

  return (
    <div 
      ref={containerRef}
      className="relative mt-4 bg-white/5 rounded-lg border border-white/10 flex flex-col group shrink-0"
      style={{ width: '100%', height: '350px' }}
    >
      <div className="flex-1 w-full h-full p-4 overflow-hidden flex flex-col min-h-0 min-w-0">
        <div className="flex-1 min-h-0 min-w-0">
          <EChartsReact
            option={new Function("echarts", "return " + config)(echarts)}
            style={{ height: "100%", width: "100%" }}
            theme="dark"
          />
        </div>
        {description && (
          <p className="text-xs text-stone mt-3 italic shrink-0 truncate">{description}</p>
        )}
      </div>
      
      {/* Resizers */}
      <div 
        className="absolute top-0 right-0 w-2.5 h-full cursor-e-resize opacity-0 group-hover:opacity-100 hover:bg-white/10 transition-all z-10 rounded-r-lg"
        onMouseDown={(e) => { e.preventDefault(); setIsDragging('right'); }}
      />
      <div 
        className="absolute bottom-0 left-0 w-full h-2.5 cursor-s-resize opacity-0 group-hover:opacity-100 hover:bg-white/10 transition-all z-10 rounded-b-lg"
        onMouseDown={(e) => { e.preventDefault(); setIsDragging('bottom'); }}
      />
      <div 
        className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize opacity-0 group-hover:opacity-100 hover:bg-white/40 transition-all z-20 rounded-br-lg"
        onMouseDown={(e) => { e.preventDefault(); setIsDragging('corner'); }}
      />
    </div>
  );
};

export const AgentPanel: React.FC<AgentPanelProps> = ({
  isVisible,
  onClose,
  onMapUpdate,
}) => {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [showLoginPage, setShowLoginPage] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [panelSize, setPanelSize] = useState<{ width: number; height: number } | null>(null);
  const [isDraggingPanel, setIsDraggingPanel] = useState<'right' | 'top' | 'corner' | null>(null);

  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isDraggingPanel) return;

    const onMouseMove = (e: MouseEvent) => {
      if (!panelRef.current) return;
      const rect = panelRef.current.getBoundingClientRect();
      
      setPanelSize(prev => {
        const currentWidth = prev?.width || rect.width;
        const currentHeight = prev?.height || rect.height;
        
        // When dragging top, we decrease the distance from bottom (height)
        let newWidth = currentWidth;
        let newHeight = currentHeight;

        if (isDraggingPanel === 'right' || isDraggingPanel === 'corner') {
          const maxWidth = document.documentElement.clientWidth - rect.left - 16; // 1rem right margin
          newWidth = Math.min(maxWidth, Math.max(400, e.clientX - rect.left));
        }
        if (isDraggingPanel === 'top' || isDraggingPanel === 'corner') {
          const maxHeight = document.documentElement.clientHeight - 32; // 1rem top + 1rem bottom margin
          newHeight = Math.min(maxHeight, Math.max(300, document.documentElement.clientHeight - e.clientY - 16));
        }
        
        return { width: newWidth, height: newHeight };
      });
    };

    const onMouseUp = () => setIsDraggingPanel(null);

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.userSelect = '';
    };
  }, [isDraggingPanel]);

  const chatScrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const processedMapUpdatesRef = useRef<Set<string>>(new Set());
  const currentChatIdRef = useRef<string | null | undefined>(undefined);
  const scrollStrategyRef = useRef<"bottom" | "lastHuman">("bottom");

  // Auto-trigger map updates
  useEffect(() => {
    if (!onMapUpdate) return;

    if (!isVisible) {
      onMapUpdate(); // Clear map highlighting when panel is closed
      return;
    }

    let convChanged = false;
    if (currentChatIdRef.current !== conversationId) {
      currentChatIdRef.current = conversationId;
      processedMapUpdatesRef.current.clear(); // Reset processed updates for new chat context
      convChanged = true;
    }

    if (messages.length === 0) {
      if (convChanged) onMapUpdate(); // Clear map if new chat is empty
      return;
    }

    const unprocessedMapMsgs = messages.filter(
      msg => msg.data?.artifact?.action === "map_update" && msg.id && !processedMapUpdatesRef.current.has(msg.id)
    );

    if (unprocessedMapMsgs.length > 0) {
      // Mark all as processed to prevent redundant triggers
      unprocessedMapMsgs.forEach(msg => processedMapUpdatesRef.current.add(msg.id as string));

      // Animate and render ONLY the latest map update
      const latestMsg = unprocessedMapMsgs[unprocessedMapMsgs.length - 1];
      const mapData = latestMsg.data?.artifact?.data || {};
      let centroid = mapData.centroid;
      
      // Handle GeoJSON Point from PostGIS
      if (centroid && centroid.type === 'Point' && Array.isArray(centroid.coordinates)) {
        centroid = centroid.coordinates as [number, number];
      }
      
      let bbox = mapData.bbox;
      if (bbox && bbox.type === 'Polygon' && Array.isArray(bbox.coordinates)) {
        const coords = bbox.coordinates[0];
        const xs = coords.map((c: any) => c[0]);
        const ys = coords.map((c: any) => c[1]);
        bbox = {
          xmin: Math.min(...xs),
          xmax: Math.max(...xs),
          ymin: Math.min(...ys),
          ymax: Math.max(...ys)
        };
      }
      
      onMapUpdate(centroid, bbox, mapData.polygon);
    } else if (convChanged) {
      // Navigated to a chat that has messages, but no map updates exist.
      onMapUpdate();
    }
  }, [messages, isVisible, conversationId, onMapUpdate]);

  // Load session on mount
  useEffect
  (() => {
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

  // Fetch conversations directly from Supabase
  const loadConversations = useCallback(async () => {
    if (!session?.user?.id) return;
    
    try {
      const { data, error } = await supabase
        .from("conversations")
        .select("id, title, created_at, updated_at")
        .eq("user_id", session.user.id)
        .order("created_at", { ascending: false });
        
      if (error) throw error;
      setConversations(data || []);
    } catch (e) {
      console.error("Failed to load conversations:", e);
    }
  }, [session]);

  // Fetch messages directly from Supabase
  const loadMessages = useCallback(async (convId: string) => {
    if (!session?.user?.id) return;
    try {
      setLoading(true);
      const { data, error } = await supabase
        .from("messages")
        .select("id, type, data")
        .eq("conversation_id", convId)
        .order("created_at", { ascending: true });

      if (error) throw error;
      
      // Strip some unnecessary keys simulating backend behavior
      const cleanedMessages: Message[] = (data || []).map((msg: any) => {
        let { content, name, tool_calls, artifact } = msg.data || {};

        if (msg.type === "ai" && tool_calls) {
          tool_calls = tool_calls.map((tc: any) => {
            const { args, ...rest } = tc;
            return rest;
          });
        }

        if (msg.type === "tool") {
          content = undefined;
          if (name === "query") {
            artifact = undefined;
          }
        }

        return {
          id: msg.id,
          type: msg.type,
          data: { content, name, tool_calls, artifact }
        };
      });

      setMessages(cleanedMessages);
      setConversationId(convId);
      scrollStrategyRef.current = "lastHuman";
    } catch (e) {
      console.error("Failed to load messages:", e);
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    if (session && isVisible) {
      loadConversations();
    }
  }, [session, isVisible, loadConversations]);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    if (isVisible && chatScrollRef.current) {
      if (scrollStrategyRef.current === "lastHuman") {
        const humanMessages = chatScrollRef.current.querySelectorAll<HTMLElement>('.human-message');
        if (humanMessages.length > 0) {
          const lastHuman = humanMessages[humanMessages.length - 1];
          chatScrollRef.current.scrollTo({
            top: Math.max(0, lastHuman.offsetTop - 20),
            behavior: "smooth"
          });
        } else {
          chatScrollRef.current.scrollTo({
            top: chatScrollRef.current.scrollHeight,
            behavior: "smooth"
          });
        }
        scrollStrategyRef.current = "bottom";
      } else {
        chatScrollRef.current.scrollTo({
          top: chatScrollRef.current.scrollHeight,
          behavior: "smooth"
        });
      }
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
  }, []);

  const createNewConversation = () => {
    setConversationId(null);
    setMessages([]);
  };

  const deleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    if (!session?.user?.id) return;
    
    const confirmDelete = window.confirm("Are you sure you want to delete this chat?");
    if (!confirmDelete) return;

    try {
      const { error } = await supabase
        .from("conversations")
        .delete()
        .eq("id", convId)
        .eq("user_id", session.user.id);
        
      if (error) throw error;
      
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (conversationId === convId) {
        createNewConversation();
      }
    } catch (e) {
      console.error("Failed to delete conversation:", e);
      alert("Failed to delete conversation.");
    }
  };

  const sendMessage = useCallback(async () => {
    if (!session) {
      setShowLoginPage(true);
      return;
    }

    const message = inputValue.trim();
    if (!message) return;

    // Add user message to display locally first
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: "human",
      data: { content: message },
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");

    try {
      setIsSending(true);
      const token = session.access_token;
      
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      const response = await fetch(
        `${import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"}/query`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            question: message,
            conversation_id: conversationId || undefined,
          }),
          signal: abortControllerRef.current.signal,
        }
      );

      if (!response.ok) {
        if (response.status === 403 || response.status === 401) setShowLoginPage(true);
        throw new Error("Failed to send message: " + response.status);
      }

      const json = await response.json();
      // The backend returns an array of messages, and may also be wrapped or directly JSON.
      // Based on agent.py, response_message (the subset) is returned directly. 
      // The list is already returned as a list of message dicts from save_conversation.
      if (Array.isArray(json)) {
        // Append these new messages to current history
        setMessages((prev) => {
          // Remove the temporary user message
          const filtered = prev.filter(p => !p.id?.startsWith("user-"));
          
          const newMessages = json.map((msg: any) => {
            const { content, name, tool_calls, artifact } = msg.data || {};
            return {
              id: msg.id,
              type: msg.type,
              data: { content, name, tool_calls, artifact }
            };
          });
          
          return [...filtered, ...newMessages];
        });
        
        // If we didn't have a conversation ID, set it to the one returned in the first message
        if (!conversationId && json.length > 0 && json[0].conversation_id) {
          setConversationId(json[0].conversation_id);
          loadConversations();
        }
      }

    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      console.error("Error sending message:", error);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        type: "ai",
        data: { content: "Sorry, there was an error processing your request." },
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsSending(false);
    }
  }, [inputValue, session, conversationId, loadConversations]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div
      ref={panelRef}
      className={`fixed 
        bottom-4 left-4 right-4
        sm:left-22 
        sm:bottom-4
        frosted-glass 
        transform transition-all duration-300 ease-in-out z-40 
        overflow-hidden
        flex
        ${
          isVisible
            ? "translate-y-0 opacity-100"
            : "translate-y-full opacity-0 pointer-events-none"
        }
      `}
      style={panelSize ? { 
        width: `${panelSize.width}px`, 
        height: `${panelSize.height}px`,
        top: 'auto',
        right: 'auto'
      } : { 
        top: '1rem',
        right: '1rem'
      }}
    >
      {/* Resizers for Panel */}
      <div 
        className="absolute top-0 right-0 w-2.5 h-full cursor-e-resize opacity-0 hover:bg-white/10 transition-all z-50 rounded-r-lg group-hover:opacity-100"
        onMouseDown={(e) => { e.preventDefault(); setIsDraggingPanel('right'); }}
      />
      <div 
        className="absolute top-0 left-0 w-full h-2.5 cursor-n-resize opacity-0 hover:bg-white/10 transition-all z-50 rounded-t-lg group-hover:opacity-100"
        onMouseDown={(e) => { e.preventDefault(); setIsDraggingPanel('top'); }}
      />
      <div 
        className="absolute top-0 right-0 w-4 h-4 cursor-ne-resize opacity-0 hover:bg-white/40 transition-all z-50 rounded-tr-lg group-hover:opacity-100"
        onMouseDown={(e) => { e.preventDefault(); setIsDraggingPanel('corner'); }}
      />

      {/* Sidebar for history */}
      <div
        className={`shrink-0 border-stone/20 bg-black/20 transition-all duration-300 ease-in-out overflow-hidden flex flex-col ${
          isSidebarOpen && session 
            ? "w-64 border-r opacity-100" 
            : "w-0 border-r-0 opacity-0"
        }`}
      >
        <div className="w-64 flex flex-col h-full">
          <div className="p-4 border-b border-stone/20 flex items-center justify-between shrink-0">
            <h3 className="text-white font-medium text-sm">Chats</h3>
            <button onClick={createNewConversation} className="p-1 hover:bg-white/10 rounded whitespace-nowrap">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto dark-scrollbar p-2 min-h-0">
            {conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => loadMessages(c.id)}
                className={`group w-full flex items-center justify-between p-2 rounded text-sm mb-1 cursor-pointer transition-colors ${conversationId === c.id ? "bg-bangladesh-green text-white" : "text-stone hover:bg-white/5"}`}
              >
                <div className="flex-1 truncate pr-2">
                  {c.title || "New Chat"}
                </div>
                <button
                  onClick={(e) => deleteConversation(e, c.id)}
                  className="shrink-0 p-1 opacity-0 group-hover:opacity-100 hover:text-red-400 focus:opacity-100 transition-opacity"
                  title="Delete chat"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0 transition-all duration-300 ease-in-out">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-stone/20">
          <div className="flex items-center gap-3">
            {session && (
              <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-1 hover:bg-white/10 rounded">
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            )}
            <h3 className="text-base font-medium text-white">Analytics Agent</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-bangladesh-green rounded-full transition-colors"
          >
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="w-full h-px bg-stone mb-4"></div>

        {/* Content */}
        {loading && session ? (
          <div className="flex items-center justify-center flex-1">
            <div className="animate-spin h-6 w-6 border-2 border-caribbean-green border-t-transparent rounded-full"></div>
          </div>
        ) : !session ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center py-8">
            <button
              onClick={() => setShowLoginPage(true)}
              className="px-6 py-2.5 bg-bangladesh-green hover:bg-mountain-meadow rounded-lg text-white"
            >
              Sign In
            </button>
          </div>
        ) : (
          <>
            {/* Messages */}
            <div ref={chatScrollRef} className="flex-1 overflow-y-auto dark-scrollbar px-6 py-4 space-y-3">
              {(() => {
                const renderedIndices = new Set<number>();
                return messages.map((msg, idx) => {
                  // Skip if already rendered as part of a tool group
                  if (renderedIndices.has(idx)) return null;

                  if (msg.type === "human") {
                    return (
                      <div key={msg.id || idx} className="human-message flex justify-end">
                        <div className="max-w-[70%] px-4 py-3 bg-bangladesh-green text-white rounded-2xl rounded-tr-sm shadow-sm break-words min-w-0">
                          <p className="text-sm whitespace-pre-wrap">{msg.data.content}</p>
                        </div>
                      </div>
                    );
                  }

                  if (msg.type === "tool") {
                    // Find all consecutive tool messages
                    const toolGroup: typeof messages = [msg];
                    let nextIdx = idx + 1;
                    
                    while (nextIdx < messages.length && messages[nextIdx].type === "tool") {
                      toolGroup.push(messages[nextIdx]);
                      renderedIndices.add(nextIdx);
                      nextIdx++;
                    }

                    return (
                      <div key={msg.id || idx} className="w-full">
                        {/* Tool badges in a flex row */}
                        <div className="flex flex-wrap gap-2">
                          {toolGroup.map((toolMsg) => (
                            <div key={toolMsg.id} className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-full text-xs text-stone font-mono flex items-center gap-2">
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                              {TOOL_DESCRIPTIONS[toolMsg.data.name] || `Ran ${toolMsg.data.name}`}
                            </div>
                          ))}
                        </div>
                        
                        {/* Artifacts below the badges */}
                        <div className="space-y-2 mt-2">
                          {toolGroup.map((toolMsg) => {
                            const toolArtifact = toolMsg.data.artifact;
                            
                            return (
                              <div key={toolMsg.id}>
                                {/* Chart artifact if present */}
                                {toolArtifact && toolArtifact.action === "render_chart" && toolArtifact.data?.config && (
                                  <div className="flex justify-start">
                                    <div className="w-full py-2 text-gray-100 pr-4">
                                      <ResizableChart 
                                        config={toolArtifact.data.config} 
                                        description={toolArtifact.description} 
                                      />
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  }

                  // AI messages
                  const artifact = msg.data.artifact;
                  const hasContent = msg.data.content;
                  const hasChartArtifact = artifact && artifact.action === "render_chart" && artifact.data?.config;

                  // Don't render if there's no content and no visible artifacts
                  if (!hasContent && !hasChartArtifact) {
                    return null;
                  }

                  return (
                    <div key={msg.id || idx} className="flex justify-start">
                      <div className="w-full max-w-none py-2 text-gray-100">
                        <div className="flex items-start gap-4">
                          <div className="w-8 h-8 rounded bg-bangladesh-green/20 flex items-center justify-center shrink-0">
                            <svg className="w-5 h-5 text-bangladesh-green" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                            </svg>
                          </div>
                          <div className="flex-1 min-w-0">
                            {msg.data.content && (
                              <div className="prose prose-invert max-w-none text-sm leading-loose">
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm]}
                                  components={{
                                    p: ({ node, ...props }) => <p className="mb-4 break-words" {...props} />,
                                    table: ({ node, ...props }) => (
                                      <div className="overflow-x-auto w-full mb-4">
                                        <table className="w-full text-left border-collapse whitespace-nowrap" {...props} />
                                      </div>
                                    ),
                                    th: ({ node, ...props }) => <th className="px-4 py-2 border-b border-white/20 font-semibold text-stone" {...props} />,
                                    td: ({ node, ...props }) => <td className="px-4 py-2 border-b border-white/10" {...props} />
                                  }}
                                >
                                  {msg.data.content}
                                </ReactMarkdown>
                              </div>
                            )}

                            {hasChartArtifact && (
                              <div className="pr-4">
                                <ResizableChart 
                                  config={artifact.data.config} 
                                  description={artifact.description} 
                                />
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                });
              })()}
            </div>

            {/* Input Element */}
            <div className="p-4 border-t border-white/10 bg-rich-black/40">
              <div className="max-w-4xl mx-auto flex gap-3 items-end">
                <textarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask the analytics agent..."
                  disabled={isSending}
                  rows={1}
                  className="flex-1 bg-white/5 border border-white/10 text-white placeholder-stone rounded-lg px-4 py-3 text-sm resize-none focus:outline-none focus:border-caribbean-green transition-colors disabled:opacity-50"
                />
                <button
                  onClick={sendMessage}
                  disabled={isSending || !inputValue.trim()}
                  className="bg-bangladesh-green hover:bg-mountain-meadow disabled:opacity-50 text-white p-3 rounded-lg transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      <LoginPage
        isVisible={showLoginPage}
        onClose={() => setShowLoginPage(false)}
        onSuccess={() => setShowLoginPage(false)}
      />
    </div>
  );
};

