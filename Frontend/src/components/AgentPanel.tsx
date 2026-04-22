import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
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

const TOOL_DESCRIPTIONS: Record<string, {active: string, done: string}> = {
  query: { active: "Fetching data", done: "Fetched data" },
  chart: { active: "Generating chart", done: "Generated chart" },
  map: { active: "Updating map", done: "Updated map" },
  examples: { active: "Reading chart examples", done: "Read chart examples" },
};

const LoadingDots = () => (
  <span className="inline-flex w-4" style={{ alignItems: 'baseline' }}>
    <span style={{ animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '-0.32s' }}>.</span>
    <span style={{ animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '-0.16s' }}>.</span>
    <span style={{ animation: 'bounce 1.4s infinite ease-in-out both' }}>.</span>
    <style>{`
      @keyframes bounce {
        0%, 80%, 100% { transform: translateY(0); }
        40% { transform: translateY(-3px); }
      }
    `}</style>
  </span>
);

const ResizableChart: React.FC<{ 
  config: string; 
  datasource?: string; 
  description?: string;
  messages: Message[];
  currentIndex: number;
}> = ({ config, datasource, description, messages, currentIndex }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState<'right' | 'bottom' | 'corner' | null>(null);

  useEffect(() => {
    if (!isDragging) return;

    const onMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const scrollParent = containerRef.current.closest('.overflow-y-auto');
      
      if (isDragging === 'right' || isDragging === 'corner') {
        const maxRight = scrollParent ? scrollParent.getBoundingClientRect().right - 32 : window.innerWidth;
        const maxWidth = Math.max(300, maxRight - rect.left);
        const newWidth = Math.min(maxWidth, Math.max(300, e.clientX - rect.left));
        containerRef.current.style.width = `${newWidth}px`;
      }
      if (isDragging === 'bottom' || isDragging === 'corner') {
        const maxBottom = scrollParent ? scrollParent.getBoundingClientRect().bottom - 16 : window.innerHeight;
        const maxHeight = Math.max(200, maxBottom - rect.top);
        const newHeight = Math.min(maxHeight, Math.max(200, e.clientY - rect.top));
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

  const { option, errorMsg } = useMemo(() => {
    try {
      let opt;
      let effectiveDatasource = datasource;

      // If datasource is missing, backtrack to find the most recent one
      if (!effectiveDatasource) {
        for (let i = currentIndex - 1; i >= 0; i--) {
          const msg = messages[i];
          const ds = msg.data?.artifact?.data?.datasource;
          if (ds) {
            effectiveDatasource = ds;
            break;
          }
        }
      }

      if (effectiveDatasource) {
        const dataObj = JSON.parse(effectiveDatasource);
        opt = new Function("echarts", "datasource", "return " + config)(echarts, dataObj);
      } else {
        opt = new Function("echarts", "return " + config)(echarts);
      }
      return { option: opt, errorMsg: null };
    } catch (e: any) {
      console.error("Failed to parse chart config:", e);
      return { option: {}, errorMsg: e.message || "Invalid chart configuration" };
    }
  }, [config, datasource, messages, currentIndex]);

  return (
    <div 
      ref={containerRef}
      className="relative mt-4 bg-white/5 rounded-lg border border-white/10 flex flex-col group shrink-0"
      style={{ width: '100%', height: '450px' }}
    >
      <div className="flex-1 w-full h-full p-4 overflow-hidden flex flex-col min-h-0 min-w-0">
        <div className="flex-1 min-h-0 min-w-0">
          {errorMsg ? (
            <div className="text-red-400 text-sm flex items-center justify-center h-full bg-red-400/10 rounded">
              Failed to render chart: {errorMsg}
            </div>
          ) : (
            <EChartsReact
              option={option}
              style={{ height: "100%", width: "100%" }}
              theme="dark"
            />
          )}
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
  const [isMobile, setIsMobile] = useState(() => typeof window !== "undefined" ? window.innerWidth < 640 : false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => typeof window !== "undefined" ? window.innerWidth >= 640 : true);
  const [panelSize, setPanelSize] = useState<{ width: number; height: number } | null>(null);
  const [isDraggingPanel, setIsDraggingPanel] = useState<'right' | 'top' | 'corner' | null>(null);

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 640;
      if (mobile !== isMobile) {
        setIsMobile(mobile);
        setIsSidebarOpen(!mobile);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [isMobile]);

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
        `${import.meta.env.VITE_AGENT_BACKEND_URL || "http://localhost:8000"}/query`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            question: message,
            conversation_id: conversationId || undefined,
            stream: true,
          }),
          signal: abortControllerRef.current.signal,
        }
      );

      if (!response.ok) {
        if (response.status === 403 || response.status === 401) setShowLoginPage(true);
        throw new Error("Failed to send message: " + response.status);
      }

      const tempId = `ai-${Date.now()}`;
      // Instead of forcing streaming logic, we'll branch based on the content type
      const contentType = response.headers.get("content-type");
      
      if (contentType && contentType.includes("text/event-stream")) {
        const tempIdsCreated = new Set<string>();
        let activeAiId = `ai-${Date.now()}`;
        tempIdsCreated.add(activeAiId);

        setMessages((prev) => [
          ...prev,
          {
            id: activeAiId,
            type: "ai",
            data: { content: "", tool_calls: [] },
          },
        ]);

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        if (!reader) throw new Error("No reader available");

        let finalMessages: any[] = [];
        let done = false;
        let buffer = "";
        let activeToolId: string | null = null;

        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          
          if (value) {
            buffer += decoder.decode(value, { stream: !done });
            let newlineIdx;
            
            while ((newlineIdx = buffer.indexOf('\n\n')) >= 0) {
              const eventStr = buffer.slice(0, newlineIdx);
              buffer = buffer.slice(newlineIdx + 2);
              
              if (eventStr.startsWith('data: ')) {
                try {
                  const data = JSON.parse(eventStr.slice(6));
                  
                  if (data.type === 'content_chunk') {
                    setMessages((prev) => {
                      const lastMsg = prev[prev.length - 1];
                      if (lastMsg && lastMsg.type === 'ai') {
                        return prev.map((p, i) => i === prev.length - 1 ? { ...p, data: { ...p.data, content: p.data.content + data.content } } : p);
                      } else {
                        activeAiId = `ai-${Date.now()}`;
                        tempIdsCreated.add(activeAiId);
                        return [...prev, { id: activeAiId, type: "ai", data: { content: data.content, tool_calls: [] } }];
                      }
                    });
                  } else if (data.type === 'tool_start') {
                    activeToolId = `tool-${data.name}-${Date.now()}`;
                    tempIdsCreated.add(activeToolId);
                    setMessages((prev) => [
                      ...prev,
                      { id: activeToolId as string, type: "tool", data: { content: "", name: data.name, _status: 'loading' } }
                    ]);
                  } else if (data.type === 'tool_end') {
                    if (activeToolId) {
                      const completeId = activeToolId; // copy to avoid closure issues
                      setMessages((prev) => 
                        prev.map(p => p.id === completeId ? { ...p, data: { ...p.data, _status: 'done', content: data.content, artifact: data.artifact } } : p)
                      );
                      activeToolId = null;
                    }
                  } else if (data.type === 'done') {
                    finalMessages = data.messages;
                    if (!conversationId && data.conversation_id) {
                      setConversationId(data.conversation_id);
                      loadConversations();
                    }
                  } else if (data.type === 'error') {
                    throw new Error(data.message);
                  }
                } catch (e) {
                  // Ignore partial JSON
                }
              }
            }
          }
        }

        if (finalMessages && finalMessages.length > 0) {
          setMessages((prev) => {
            const filtered = prev.filter(p => !p.id?.startsWith("user-") && (p.id ? !tempIdsCreated.has(p.id) : true));
            const newMessages = finalMessages.map((msg: any) => ({
              id: msg.id,
              type: msg.type,
              data: msg.data || {}
            }));
            return [...filtered, ...newMessages];
          });
        }
      } else {
        // Non-streaming fallback
        const responseData = await response.json();
        
        if (responseData.messages && Array.isArray(responseData.messages)) {
          setMessages((prev) => {
            const filtered = prev.filter(p => !p.id?.startsWith("user-"));
            const newMessages = responseData.messages.map((msg: any) => ({
              id: msg.id, type: msg.type, data: msg.data || {}
            }));
            return [...filtered, ...newMessages];
          });
          
          if (!conversationId && responseData.conversation_id) {
            setConversationId(responseData.conversation_id);
            loadConversations();
          }
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
      style={panelSize && !isMobile ? { 
        width: `${panelSize.width}px`, 
        height: `${panelSize.height}px`,
        top: 'auto',
        right: 'auto'
      } : { 
        top: isMobile ? '5rem' : '1rem',
        right: isMobile ? '1rem' : '1rem'
      }}
    >
      {/* Resizers for Panel */}
      <div 
        className="hidden sm:block absolute top-0 right-0 w-2.5 h-full cursor-e-resize opacity-0 hover:bg-white/10 transition-all z-50 rounded-r-lg group-hover:opacity-100"
        onMouseDown={(e) => { e.preventDefault(); setIsDraggingPanel('right'); }}
      />
      <div 
        className="hidden sm:block absolute top-0 left-0 w-full h-2.5 cursor-n-resize opacity-0 hover:bg-white/10 transition-all z-50 rounded-t-lg group-hover:opacity-100"
        onMouseDown={(e) => { e.preventDefault(); setIsDraggingPanel('top'); }}
      />
      <div 
        className="hidden sm:block absolute top-0 right-0 w-4 h-4 cursor-ne-resize opacity-0 hover:bg-white/40 transition-all z-50 rounded-tr-lg group-hover:opacity-100"
        onMouseDown={(e) => { e.preventDefault(); setIsDraggingPanel('corner'); }}
      />

      {/* Sidebar for history */}
      <div
        className={`shrink-0 border-stone/20 bg-rich-black/95 backdrop-blur-sm sm:bg-black/20 transition-all duration-300 ease-in-out overflow-hidden flex flex-col ${
          isMobile ? "absolute inset-y-0 left-0 z-50" : "relative"
        } ${
          isSidebarOpen && session 
            ? (isMobile ? "w-full border-r opacity-100" : "w-64 border-r opacity-100") 
            : "w-0 border-r-0 opacity-0"
        }`}
      >
        <div className={`${isMobile ? 'w-full' : 'w-64'} flex flex-col h-full`}>
          <div className="p-4 border-b border-stone/20 flex items-center justify-between shrink-0">
            <h3 className="text-white font-medium text-sm">Chats</h3>
            <div className="flex items-center gap-1">
              <button onClick={() => { createNewConversation(); if(isMobile) setIsSidebarOpen(false); }} className="p-1 hover:bg-white/10 rounded whitespace-nowrap">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
              {isMobile && (
                <button onClick={() => setIsSidebarOpen(false)} className="p-1 hover:bg-white/10 rounded whitespace-nowrap">
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto dark-scrollbar p-2 min-h-0">
            {conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => { loadMessages(c.id); if(isMobile) setIsSidebarOpen(false); }}
                className={`group w-full flex items-center justify-between p-3 text-sm mb-2 cursor-pointer transition-colors ${conversationId === c.id ? "bg-bangladesh-green text-white" : "text-stone hover:bg-white/5"}`}
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
            <h3 className="text-base font-medium text-white">REACH Agent</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-white/20 hover:text-white rounded transition-colors"
          >
            <svg className="w-4 h-4 text-gray-400 hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                      <div key={msg.id || idx} className="human-message flex justify-end group items-center gap-2">
                        <button
                          onClick={() => navigator.clipboard.writeText(msg.data.content)}
                          className="opacity-0 group-hover:opacity-100 p-1.5 text-stone hover:text-white hover:bg-white/10 rounded transition-all"
                          title="Copy message"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                        </button>
                        <div className="max-w-[70%] px-4 py-3 bg-bangladesh-green text-white shadow-sm break-words min-w-0">
                          <p className="text-sm whitespace-pre-wrap">{msg.data.content}</p>
                        </div>
                      </div>
                    );
                  }

                  if (msg.type === "tool") {
                    // Find all consecutive tool messages (skipping empty AI intermediate steps)
                    const toolGroup: typeof messages = [msg];
                    let nextIdx = idx + 1;
                    
                    while (nextIdx < messages.length) {
                      const nextMsg = messages[nextIdx];
                      if (nextMsg.type === "tool") {
                        toolGroup.push(nextMsg);
                        renderedIndices.add(nextIdx);
                        nextIdx++;
                      } else if (
                        nextMsg.type === "ai" && 
                        !nextMsg.data.content && 
                        !(nextMsg.data.artifact && nextMsg.data.artifact.action === "render_chart" && nextMsg.data.artifact.data?.config)
                      ) {
                        // Skip empty AI messages that generated the tool calls
                        renderedIndices.add(nextIdx);
                        nextIdx++;
                      } else {
                        break;
                      }
                    }

                    return (
                      <div key={msg.id || idx} className="w-full">
                        {/* Tool badges in a flex row */}
                        <div className="flex flex-wrap gap-2">
                          {toolGroup.map((toolMsg) => {
                            const isloading = toolMsg.data._status === 'loading';
                            const descObj = TOOL_DESCRIPTIONS[toolMsg.data.name];
                            const badgeText = descObj 
                                ? (isloading ? descObj.active : descObj.done) 
                                : (isloading ? `Running ${toolMsg.data.name}` : `Ran ${toolMsg.data.name}`);

                            return (
                              <div key={toolMsg.id} className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-full text-xs text-stone font-mono flex items-center gap-2">
                                <svg className={`w-3 h-3 ${isloading ? 'animate-spin text-caribbean-green' : 'text-stone'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                </svg>
                                <span>{badgeText}</span>
                                {isloading && <LoadingDots />}
                              </div>
                            );
                          })}
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
                                        datasource={toolArtifact.data.datasource}
                                        description={toolArtifact.description}
                                        messages={messages}
                                        currentIndex={idx}
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
                              <div className="prose prose-invert prose-p:leading-relaxed prose-pre:p-0 prose-pre:bg-transparent prose-pre:m-0 max-w-none text-sm">
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm]}
                                  components={{
                                    h1: ({ node, ...props }) => <h1 className="text-2xl font-semibold text-white mt-6 mb-4" {...props} />,
                                    h2: ({ node, ...props }) => <h2 className="text-xl font-semibold text-white mt-5 mb-3" {...props} />,
                                    h3: ({ node, ...props }) => <h3 className="text-lg font-medium text-white mt-4 mb-2" {...props} />,
                                    ul: ({ node, ...props }) => <ul className="list-disc list-outside ml-6 mb-4 space-y-1 marker:text-stone" {...props} />,
                                    ol: ({ node, ...props }) => <ol className="list-decimal list-outside ml-6 mb-4 space-y-1 marker:text-stone" {...props} />,
                                    li: ({ node, ...props }) => <li className="pl-1 text-gray-300" {...props} />,
                                    a: ({ node, ...props }) => <a className="text-caribbean-green hover:text-mountain-meadow underline underline-offset-2" target="_blank" rel="noopener noreferrer" {...props} />,
                                    blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-bangladesh-green pl-4 my-4 italic text-stone bg-white/5 py-2 rounded-r" {...props} />,
                                    pre: ({ node, children, ...props }: any) => {
                                      const childrenArray = React.Children.toArray(children);
                                      const codeElement = childrenArray[0] as any;
                                      const codeProps: any = React.isValidElement(codeElement) ? codeElement.props : {};
                                      const className = codeProps?.className || '';
                                      const match = /language-(\w+)/.exec(className);
                                      
                                      return (
                                        <div className="not-prose rounded-lg bg-black/50 border border-white/10 my-4 overflow-hidden">
                                          {match && <div className="bg-white/5 px-4 py-1.5 text-xs text-stone font-mono border-b border-white/10 capitalize">{match[1]}</div>}
                                          <div className="p-4 overflow-x-auto dark-scrollbar">
                                            <code className={`font-mono text-sm text-gray-300 ${className}`}>
                                              {codeProps?.children || children}
                                            </code>
                                          </div>
                                        </div>
                                      );
                                    },
                                    code: ({ node, className, children, ...props }: any) => (
                                      <code className="bg-white/10 text-white px-1.5 py-0.5 border border-white/10 rounded font-mono text-[0.9em]" {...props}>
                                        {children}
                                      </code>
                                    ),
                                    p: ({ node, ...props }) => <p className="mb-4 break-words text-gray-200" {...props} />,
                                    hr: ({ node, ...props }) => <hr className="my-6 border-t border-white/20" {...props} />,
                                    table: ({ node, ...props }) => (
                                      <div className="not-prose overflow-x-auto w-full mb-4 rounded-lg border border-white/10">
                                        <table className="w-full text-left border-collapse whitespace-nowrap bg-black/20" {...props} />
                                      </div>
                                    ),
                                    th: ({ node, ...props }) => <th className="px-4 py-3 border-b border-r last:border-r-0 border-white/20 font-semibold text-white bg-white/5" {...props} />,
                                    td: ({ node, ...props }) => <td className="px-4 py-3 border-b border-r last:border-r-0 border-white/10 text-gray-300" {...props} />
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
                                  datasource={artifact.data.datasource}
                                  description={artifact.description}
                                  messages={messages}
                                  currentIndex={idx}
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
                  className="bg-bangladesh-green hover:brightness-125 disabled:cursor-not-allowed text-white p-3 rounded-lg transition-all"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
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

