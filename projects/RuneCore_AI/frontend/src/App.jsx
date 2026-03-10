import React, {
  useState,
  useEffect,
  useRef,
  useMemo,
  useCallback,
} from "react";
import "./theme.css";
import ReactMarkdown from "react-markdown";
import { logFrontendError } from "./utils/errorLogger";
import CreateAgentModal from "./components/CreateAgentModal";
import EditAgentModal from "./components/EditAgentModal";
import ModelManager from "./components/ModelManager";
import UserProfileModal from "./components/UserProfileModal";
import HardwarePanel from "./components/HardwarePanel";

// API base URL
const API_BASE = process.env.REACT_APP_API_URL || "";

// Pre-computed avatar colors for better performance
const AVATAR_COLORS = [
  "#6b46c1",
  "#7c3aed",
  "#8b5cf6",
  "#a855f7",
  "#c084fc",
  "#4c1d95",
  "#5b21b6",
  "#6d28d9",
  "#7c2d12",
  "#92400e",
];

// Optimized helper functions (moved outside component to prevent re-creation)
const getAvatarColor = (name) => {
  if (!name || typeof name !== "string" || name.length === 0) {
    return AVATAR_COLORS[0];
  }
  return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];
};

const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
};

const calculateDowntime = (lastActive) => {
  if (!lastActive) return "Never active";
  const now = Date.now();
  const last = new Date(lastActive).getTime();
  const diffMins = Math.floor((now - last) / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  if (diffMins > 0) return `${diffMins}m ago`;
  return "Just now";
};

const getAgentStatusDisplay = (agent, isThinking = false) => {
  // If agent is currently thinking, show as busy
  if (isThinking) {
    return { text: "busy", class: "busy" };
  }

  // Determine downtime
  if (!agent || !agent.last_active) {
    return { text: "online", class: "idle" };
  }

  const lastActiveTime = new Date(agent.last_active).getTime();
  const now = Date.now();
  const downtime = now - lastActiveTime;

  // If more than 5 minutes inactive, show as online
  if (downtime > 300000) {
    return { text: "online", class: "idle" };
  }

  switch (agent.status) {
    case "idle":
      return { text: "online", class: "idle" };
    case "busy":
      return { text: "busy", class: "busy" };
    default:
      return { text: agent.status, class: agent.status };
  }
};

function App() {
  // State management (optimized with lazy initial state where appropriate)
  const [agents, setAgents] = useState([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(null);
  // Ref that mirrors selectedAgent so async handlers can read the CURRENT value without stale closures
  const selectedAgentRef = useRef(null);
  const [messages, setMessages] = useState([]);
  // Per-agent message store: { [agentId]: Message[] }
  const [messageStore, setMessageStore] = useState({});
  
  // Helper to trim message store to last 10 messages (matching backend limit)
  const trimMessageStore = (store, agentId, messages) => {
    const trimmed = messages.slice(-10);
    return { ...store, [agentId]: trimmed };
  };
  const [inputText, setInputText] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [thinkingAgents, setThinkingAgents] = useState(new Set()); // Track which agents are thinking
  const [unreadCounts, setUnreadCounts] = useState({}); // Track unread messages per agent
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [agentToEdit, setAgentToEdit] = useState(null);
  const [showModelManager, setShowModelManager] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showHardwarePanel, setShowHardwarePanel] = useState(false);
  const [hardwareDevices, setHardwareDevices] = useState([]);
  const [hardwareOptimised, setHardwareOptimised] = useState(false);
  const [hwStatus, setHwStatus] = useState("idle"); // idle | running | done | error
  const [hwSteps, setHwSteps] = useState([]);
  const [hwDevices, setHwDevices] = useState([]);
  const [cacheStatus, setCacheStatus] = useState(null);

  // Poll hardware optimise task while running (continues even if panel is closed)
  useEffect(() => {
    if (hwStatus !== "running") return;
    const iv = setInterval(async () => {
      try {
        const r = await fetch(`${API_BASE}/api/hardware/optimise/status`);
        if (!r.ok) return;
        const data = await r.json();
        setHwSteps(data.steps || []);
        if (data.status !== "running") {
          setHwStatus(data.status);
          if (data.devices && data.devices.length > 0) {
            setHwDevices(data.devices);
            setHardwareDevices(data.devices);
          }
          if (data.status === "done") setHardwareOptimised(true);
          clearInterval(iv);
        }
      } catch (_) {}
    }, 1500);
    return () => clearInterval(iv);
  }, [hwStatus]);

  const handleStartOptimise = useCallback(async () => {
    setHwStatus("running");
    setHwSteps([]);
    setHwDevices([]);
    try {
      await fetch(`${API_BASE}/api/hardware/optimise`, { method: "POST" });
    } catch (e) {
      setHwStatus("error");
    }
  }, []);

  // Model retry/cancel helpers: when backend reports a model pull timeout we
  // start a background retry loop and present a Cancel button to the user.
  const [modelRetryingAgent, setModelRetryingAgent] = useState(null);
  const modelRetryCancelRef = useRef({});

  const startBackgroundRetry = (userMessage, agentId, initialErrorCode) => {
    // Mark retrying state
    setModelRetryingAgent(agentId);
    modelRetryCancelRef.current[agentId] = false;

    const baseMs = parseInt(process.env.REACT_APP_MODEL_RETRY_BASE_MS || "2000", 10);
    const maxBackoffPow = 6; // cap exponent to avoid huge waits

    (async () => {
      let attempt = 0;
      while (!modelRetryCancelRef.current[agentId]) {
        attempt += 1;
        const waitMs = baseMs * Math.pow(2, Math.min(attempt - 1, maxBackoffPow));
        // wait before retrying
        await new Promise((res) => setTimeout(res, waitMs));

        try {
          const retryResp = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: userMessage, agent_id: agentId }),
          });

          const retryData = await retryResp.json().catch(() => ({}));

          if (retryResp.ok) {
            // Replace previous model-missing messages and append the successful response
            const successMsg = {
              id: Date.now() + Math.random(),
              sender: "ai",
              text: retryData.response,
              timestamp: new Date().toISOString(),
              agentId: agentId,
            };
            setMessageStore((prev) => {
              const list = (prev[agentId] || []).filter((m) => m.errorCode !== initialErrorCode).concat([successMsg]);
              return trimMessageStore(prev, agentId, list);
            });
            if (agentId === selectedAgentRef.current) {
              setMessages((prev) => prev.filter((m) => m.errorCode !== initialErrorCode).concat([successMsg]));
            }
            logFrontendError("FRONTEND_CHAT_SUCCESS_RETRY_BG", "Background retry succeeded", { attempt, agentId });
            // clear thinking and retrying state
            setThinkingAgents((prev) => {
              const newSet = new Set(prev);
              newSet.delete(agentId);
              return newSet;
            });
            delete modelRetryCancelRef.current[agentId];
            break;
          } else {
            // update the visible status message so user knows we're still trying
            const interim = {
              id: Date.now() + Math.random(),
              sender: "ai",
              text: retryData.message || `Attempt ${attempt} failed; still trying...`,
              timestamp: new Date().toISOString(),
              agentId,
              error: true,
              errorCode: retryData.error_code || initialErrorCode,
            };
            setMessageStore((prev) => {
              const list = (prev[agentId] || []).filter((m) => m.errorCode !== initialErrorCode).concat([interim]);
              return trimMessageStore(prev, agentId, list);
            });
            if (agentId === selectedAgentRef.current) {
              setMessages((prev) => prev.filter((m) => m.errorCode !== initialErrorCode).concat([interim]));
            }
          }
        } catch (err) {
          const netErr = {
            id: Date.now() + Math.random(),
            sender: "ai",
            text: `Network error during retry; still trying...`,
            timestamp: new Date().toISOString(),
            agentId,
            error: true,
          };
          setMessageStore((prev) => {
            const list = (prev[agentId] || []).filter((m) => m.errorCode !== initialErrorCode).concat([netErr]);
            return trimMessageStore(prev, agentId, list);
          });
          if (agentId === selectedAgentRef.current) {
            setMessages((prev) => prev.filter((m) => m.errorCode !== initialErrorCode).concat([netErr]));
          }
        }
      }

      if (modelRetryCancelRef.current[agentId]) {
        // User canceled: inform in chat and clear thinking indicator
        const cancelMsg = {
          id: Date.now() + Math.random(),
          sender: "ai",
          text: "Model download canceled by user.",
          timestamp: new Date().toISOString(),
          agentId,
          error: true,
          errorCode: "E_MODEL_PULL_CANCELED",
        };
        setMessageStore((prev) => {
          const list = (prev[agentId] || []).filter((m) => m.errorCode !== initialErrorCode).concat([cancelMsg]);
          return trimMessageStore(prev, agentId, list);
        });
        if (agentId === selectedAgentRef.current) {
          setMessages((prev) => prev.filter((m) => m.errorCode !== initialErrorCode).concat([cancelMsg]));
        }
        setThinkingAgents((prev) => {
          const newSet = new Set(prev);
          newSet.delete(agentId);
          return newSet;
        });
        setModelRetryingAgent(null);
        delete modelRetryCancelRef.current[agentId];
      }
    })();
  };

  const cancelModelRetry = (agentId) => {
    if (!agentId) agentId = selectedAgent;
    modelRetryCancelRef.current[agentId] = true;
    // UI state cleanup will be handled by the background loop
    logFrontendError("FRONTEND_MODEL_PULL_CANCELED", "User canceled model pull retry", { agentId });
  };

  // Keep selectedAgentRef in sync so async handlers can read the current value
  useEffect(() => {
    selectedAgentRef.current = selectedAgent;
  }, [selectedAgent]);

  // Auto-resize textarea to fit content (resets when inputText is cleared)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }, [inputText]);

  const fileInputRef = useRef(null);
  const chatAreaRef = useRef(null);
  const textareaRef = useRef(null);

  // Memoized values for performance
  const currentAgent = useMemo(
    () => agents.find((a) => a.id === selectedAgent),
    [agents, selectedAgent]
  );

  const validAgents = useMemo(
    () =>
      agents.filter(
        (agent) => agent && typeof agent === "object" && agent.id && agent.name
      ),
    [agents]
  );

  // Optimized API calls with useCallback
  const loadAgents = useCallback(async () => {
    try {
      setAgentsLoading((prev) => prev); // keep loading state on refresh without flash
      const response = await fetch(`${API_BASE}/api/agents`);
      if (response.ok) {
        const data = await response.json();
        const incoming = (data.agents || []).filter(
          (agent) =>
            agent && typeof agent === "object" && agent.id && agent.name
        );

        // Smart merge: only update state if something actually changed.
        // This prevents the full list from disappearing and reappearing on
        // each polling tick.
        setAgents((prev) => {
          const prevMap = new Map(prev.map((a) => [a.id, a]));
          const inMap = new Map(incoming.map((a) => [a.id, a]));

          // Check for deletions or additions
          const sameIds =
            prev.length === incoming.length &&
            incoming.every((a) => prevMap.has(a.id));

          if (sameIds) {
            // Same set of agents — only replace entries that actually changed
            const merged = prev.map((a) => {
              const fresh = inMap.get(a.id);
              if (!fresh) return a;
              // Shallow compare a few key fields to avoid unnecessary re-renders
              if (
                a.name === fresh.name &&
                a.model_name === fresh.model_name &&
                a.status === fresh.status &&
                a.last_active === fresh.last_active
              ) {
                return a; // no change — return same reference
              }
              return fresh;
            });
            return merged;
          }

          // Agent list changed (add/remove) — use fresh list
          return incoming;
        });

        // Set first agent as selected if none selected
        if (incoming.length > 0 && !selectedAgent) {
          setSelectedAgent(incoming[0].id);
        }
      }
    } catch (error) {
      logFrontendError("AGENTS_LOAD_ERROR", "Failed to load agents", error);
    } finally {
      setAgentsLoading(false);
    }
  }, [selectedAgent]);

  const loadConversationHistory = useCallback(async (agentId) => {
    try {
      const response = await fetch(
        `${API_BASE}/api/agents/${agentId}/conversations?limit=50`
      );
      if (response.ok) {
        const data = await response.json();
        const conversations = data.conversations || [];

        // Convert conversation logs to message format
        const historyMessages = conversations.flatMap((conv) => [
          {
            id: `${conv.id}-user`,
            sender: "user",
            text: conv.user_message,
            timestamp: conv.timestamp,
          },
          {
            id: `${conv.id}-ai`,
            sender: "ai",
            text: conv.ai_response,
            timestamp: conv.timestamp,
            model: conv.model_used,
          },
        ]);

        // Save into per-agent store and return the messages
        setMessageStore((prev) => ({ ...prev, [agentId]: historyMessages }));
        return historyMessages;
        logFrontendError(
          "CONVERSATION_HISTORY_LOADED",
          `Loaded ${conversations.length} conversations for agent ${agentId}`
        );
      }
    } catch (error) {
      logFrontendError(
        "CONVERSATION_HISTORY_ERROR",
        `Failed to load conversation history for agent ${agentId}`,
        error
      );
      // Keep any existing store for the agent, but clear visible messages if currently selected
      setMessageStore((prev) => ({ ...prev, [agentId]: prev[agentId] || [] }));
      return [];
    }
  }, []);

  const handleAgentSwitch = useCallback(
    async (agentId) => {
      if (agentId === selectedAgent) return;

      // Switch selection and restore stored messages (or load from backend)
      setSelectedAgent(agentId);
      setInputText("");

      // Clear unread count for this agent
      setUnreadCounts((prev) => ({ ...prev, [agentId]: 0 }));

      const stored = messageStore[agentId];
      if (stored && stored.length > 0) {
        // Immediately show stored messages for this agent
        setMessages(stored);
      } else {
        // Immediately clear so we don't show the previous agent's messages
        setMessages([]);
        // Load from backend and populate store
        if (agentId) {
          const history = await loadConversationHistory(agentId);
          setMessages(history || []);
        }
      }
    },
    [selectedAgent, loadConversationHistory, messageStore]
  );

  const handleSend = useCallback(async () => {
    const isAgentThinking = thinkingAgents.has(selectedAgent);
    if (connecting || !inputText.trim() || isAgentThinking) return;

    // If true, we will keep the agent in the thinking state (used for EABB5)
    let keepThinkingVisible = false;

    const userMessage = inputText.trim();
    setInputText("");

    // Mark this agent as thinking
    setThinkingAgents((prev) => new Set([...prev, selectedAgent]));
    // Capture agent id for this send operation to avoid race conditions
    const agentIdNow = selectedAgent;

    // Generate unique IDs once
    const messageId = Date.now() + Math.random();
    const thinkingId = messageId + 1;
    const timestamp = new Date().toISOString();

    // Add user message
    const newMessage = {
      id: messageId,
      sender: "user",
      text: userMessage,
      timestamp,
      files: selectedFiles.length > 0 ? [...selectedFiles] : undefined,
    };
    // Persist the new user message into the per-agent store (limit to 10)
    setMessageStore((prev) => {
      const cur = (prev[agentIdNow] || []).concat([newMessage]);
      return trimMessageStore(prev, agentIdNow, cur);
    });
    // Update visible messages only if still viewing this agent
    if (agentIdNow === selectedAgent) {
      setMessages((prev) => [...prev, newMessage]);
    }
    setSelectedFiles([]);

    // Add thinking indicator
    const thinkingMsg = {
      id: thinkingId,
      sender: "ai",
      text: "Thinking...",
      timestamp,
      isThinking: true,
      agentId: agentIdNow,
    };
    setMessageStore((prev) => {
      const cur = (prev[agentIdNow] || []).concat([thinkingMsg]);
      return trimMessageStore(prev, agentIdNow, cur);
    });
    // Update visible messages only if still viewing this agent
    if (agentIdNow === selectedAgent) {
      setMessages((prev) => [...prev, thinkingMsg]);
    }

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          agent_id: selectedAgent,
        }),
      });

      // Check if response is JSON before parsing
      const contentType = response.headers.get("content-type");
      let data;
      try {
        if (contentType && contentType.includes("application/json")) {
          data = await response.json();
        } else {
          // Got HTML or other non-JSON response (nginx error page)
          const text = await response.text();
          throw new Error(`Server returned non-JSON response (${response.status}): ${text.substring(0, 100)}`);
        }
      } catch (parseError) {
        throw new Error(`Failed to parse server response: ${parseError.message}`);
      }

      // Model-missing codes that require the CANCEL/retry flow.
      // Checked both inside response.ok (HTTP 202 "accepted") and the error branch.
      const modelMissingCodes = new Set([
        "E_MODEL_MISSING",
        "E_MODEL_MISSING_PULL_TIMEOUT",
        "E_MODEL_MISSING_PULL_STARTED",
        "E_MODEL_PULL_IN_PROGRESS",   // backend returns HTTP 202 for this
        "MODEL_PULL_IN_PROGRESS",     // alternate form
      ]);

      // HTTP 202 is response.ok===true but means "model pull started, retry later".
      // Detect it by checking error_code in the body before treating as success.
      const isModelPull202 = response.status === 202 && data && modelMissingCodes.has(data.error_code);

      if (response.ok && !isModelPull202) {
        // Remove thinking message and add AI response
        const aiMsg = {
          id: Date.now() + Math.random(),
          sender: "ai",
          text: data.response,
          timestamp: new Date().toISOString(),
          agentId: agentIdNow,
        };

        setMessageStore((prev) => {
          const list = (prev[agentIdNow] || []).filter((msg) => msg.id !== thinkingId).concat([aiMsg]);
          return trimMessageStore(prev, agentIdNow, list);
        });

        // Use the ref to read the CURRENT selected agent — avoids stale closure and
        // avoids calling setMessages inside setSelectedAgent which can cause extra renders
        if (agentIdNow === selectedAgentRef.current) {
          // Still viewing this agent — update visible messages
          setMessages((prev) => prev.filter((msg) => msg.id !== thinkingId).concat([aiMsg]));
        } else {
          // User switched to a different agent — increment unread badge only
          setUnreadCounts((counts) => ({
            ...counts,
            [agentIdNow]: (counts[agentIdNow] || 0) + 1,
          }));
        }

        logFrontendError(
          "FRONTEND_CHAT_SUCCESS",
          "Chat message sent successfully"
        );
      } else {
        // Handle specific backend error codes for model-missing and upstream failures.
        // modelMissingCodes is defined above and shared with the 202 check.
        if (data && data.error_code === "EABB5") {
          // Upstream AI unavailable — show error and let user retry manually.
          // Do NOT keep thinking visible (no background retry is started for this case).
          const serverMsg = data.message || "Upstream AI service unavailable. Please retry.";
          const eabbMsg = {
            id: Date.now() + Math.random(),
            sender: "ai",
            text: serverMsg,
            timestamp: new Date().toISOString(),
            agentId: agentIdNow,
            error: true,
            errorCode: "EABB5",
          };
          setMessageStore((prev) => {
            const list = (prev[agentIdNow] || []).filter((m) => m.id !== thinkingId).concat([eabbMsg]);
            return trimMessageStore(prev, agentIdNow, list);
          });
          if (agentIdNow === selectedAgentRef.current) {
            setMessages((prev) => prev.filter((m) => m.id !== thinkingId).concat([eabbMsg]));
          }
          // keepThinkingVisible stays false — this releases the textarea so user can retry
          logFrontendError("FRONTEND_CHAT_EABB5", "Received EABB5 from backend", data);
        } else if (data && modelMissingCodes.has(data.error_code)) {
          // Model missing: instead of immediately failing, start a background
          // retry loop and show a Cancel button so the user can stop attempts.
          const modelMissingMsg = {
            id: Date.now() + Math.random(),
            sender: "ai",
            text: data.message || "Requested model is not available. We are attempting to download it — press Cancel to stop.",
            timestamp: new Date().toISOString(),
            agentId: agentIdNow,
            error: true,
            errorCode: data.error_code,
          };
          setMessageStore((prev) => {
            const list = (prev[agentIdNow] || []).concat([modelMissingMsg]);
            return trimMessageStore(prev, agentIdNow, list);
          });
          if (agentIdNow === selectedAgentRef.current) {
            setMessages((prev) => [...prev, modelMissingMsg]);
          }

          // Keep the thinking indicator visible while background retries proceed
          keepThinkingVisible = true;

          // Start background retries (non-blocking)
          try {
            startBackgroundRetry(userMessage, agentIdNow, data.error_code);
            logFrontendError("FRONTEND_MODEL_PULL_WAITING", "Started background retries for missing model", { agentId: agentIdNow, error_code: data.error_code });
          } catch (err) {
            logFrontendError("FRONTEND_MODEL_PULL_WAIT_ERR", "Failed to start background retry", err);
          }
        } else {
          let errorMessage = "Sorry, I couldn't process your message. ";

          if (data.message) {
            errorMessage = data.message;
          } else if (data.error) {
            switch (data.error) {
              case "AI service unavailable":
                errorMessage =
                  "The AI service is currently offline. Please wait a moment and try again.";
                break;
              case "AI processing failed":
                errorMessage =
                  "I'm having trouble understanding your message. Could you try rephrasing it?";
                break;
              case "Empty message":
                errorMessage = "Please type a message to send.";
                break;
              default:
                errorMessage = data.error;
            }
          }

          throw new Error(errorMessage);
        }
      }
    } catch (error) {
      let userFriendlyMessage = "Sorry, something went wrong. ";

      if (error.message) {
        userFriendlyMessage = error.message;
      } else if (error.name === "TypeError" || error.name === "NetworkError") {
        userFriendlyMessage =
          "Can't connect to the AI service. Please check your internet connection and try again.";
      }

      const errMsg = {
        id: Date.now() + Math.random(),
        sender: "ai",
        text: userFriendlyMessage,
        timestamp: new Date().toISOString(),
        error: true,
        agentId: agentIdNow,
      };
      
      // If network error, show connection lost indicator
      if (error.name === "TypeError" || error.name === "NetworkError" || userFriendlyMessage.includes("Can't connect")) {
        setConnecting(true);
      }
      
      setMessageStore((prev) => {
        const list = (prev[agentIdNow] || []).filter((msg) => msg.id !== thinkingId).concat([errMsg]);
        return trimMessageStore(prev, agentIdNow, list);
      });
      if (agentIdNow === selectedAgentRef.current) {
        setMessages((prev) => prev.filter((msg) => msg.id !== thinkingId).concat([errMsg]));
      }
      logFrontendError("FRONTEND_CHAT_ERROR", "Chat request failed", error);
    }

    // Remove this agent from thinking set unless we intentionally
    // want to keep the thinking indicator visible (EABB5 case)
    if (!keepThinkingVisible) {
      setThinkingAgents((prev) => {
        const newSet = new Set(prev);
        newSet.delete(agentIdNow);
        return newSet;
      });
    }
  }, [connecting, inputText, thinkingAgents, selectedFiles, selectedAgent]);

  // Check backend connection and load agents on mount
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const response = await fetch(`${API_BASE}/health`);
        if (response.ok) {
          setConnecting(false);
          await loadAgents();
        }
      } catch (error) {
        logFrontendError(
          "BACKEND_CONNECTION_ERROR",
          "Failed to connect to backend",
          error
        );
        setConnecting(true);
        setTimeout(checkBackend, 5000);
      }
    };

    checkBackend();

    // Set up periodic agent refresh (less aggressive to prevent flickering)
    const refreshInterval = setInterval(async () => {
      if (!connecting) {
        try {
          await loadAgents();
        } catch (error) {
          // Silently fail on refresh errors to prevent UI disruption
          console.error("Agent refresh failed:", error);
        }
      }
    }, 30000); // Reduced from 5s to 30s to prevent flickering

    // Poll cache status separately so the UI can surface memory-core availability
    const loadCacheStatus = async () => {
      if (connecting) return;
      try {
        const r = await fetch(`${API_BASE}/api/cache/stats`);
        if (r.ok) {
          const d = await r.json();
          setCacheStatus(d);
        }
      } catch (e) {
        setCacheStatus({ cache: { using_redis: false } });
      }
    };
    loadCacheStatus();
    const cacheIv = setInterval(loadCacheStatus, 5000);

    // Fetch hardware status once on connect to populate device list for placement picker
    const loadHardwareStatus = async () => {
      if (connecting) return;
      try {
        const r = await fetch(`${API_BASE}/api/hardware/status`);
        if (r.ok) {
          const d = await r.json();
          setHardwareDevices(d.devices || []);
        }
      } catch (e) {
        // Non-fatal — hardware panel will show empty state
      }
    };
    loadHardwareStatus();

    return () => {
      clearInterval(refreshInterval);
      clearInterval(cacheIv);
    };
  }, [connecting, loadAgents]);

  // Auto scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // Event handlers (optimized with useCallback)
  const handleKeyPress = useCallback(
    (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleFileSelect = useCallback((e) => {
    const files = Array.from(e.target.files);
    setSelectedFiles((prev) => [...prev, ...files]);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    setSelectedFiles((prev) => [...prev, ...files]);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const removeFile = useCallback((index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // Agent management handlers
  const handleAgentCreated = useCallback(
    async (newAgent) => {
      setAgents((prev) => [newAgent, ...prev]);
      await handleAgentSwitch(newAgent.id);
      logFrontendError(
        "FRONTEND_AGENT_CREATED",
        `Created agent: ${newAgent.name}`
      );
    },
    [handleAgentSwitch]
  );

  const handleEditAgent = useCallback((agent) => {
    setAgentToEdit(agent);
    setShowEditModal(true);
    setToolsOpen(false);
  }, []);

  const handleAgentUpdated = useCallback((updatedAgent) => {
    setAgents((prev) =>
      prev.map((agent) => (agent.id === updatedAgent.id ? updatedAgent : agent))
    );
    logFrontendError(
      "FRONTEND_AGENT_UPDATED",
      `Updated agent: ${updatedAgent.name}`
    );
  }, []);

  const handleAgentDeleted = useCallback(
    async (deletedAgentId) => {
      setAgents((prev) => prev.filter((agent) => agent.id !== deletedAgentId));

      if (selectedAgent === deletedAgentId) {
        const remainingAgents = agents.filter(
          (agent) => agent.id !== deletedAgentId
        );
        if (remainingAgents.length > 0) {
          await handleAgentSwitch(remainingAgents[0].id);
        } else {
          setSelectedAgent(null);
          setMessages([]);
        }
      }

      logFrontendError(
        "FRONTEND_AGENT_DELETED",
        `Deleted agent: ${deletedAgentId}`
      );
    },
    [selectedAgent, agents, handleAgentSwitch]
  );

  return (
    <div className="app">
      {/* Top Bar */}
      <div className="top-bar">
        <div className="brand">
          <span className="brand-mark">▲</span>
          <span className="brand-name">RuneCore Mind</span>
        </div>
        <div className="top-bar-spacer" />
        <div className="top-bar-status">
          {cacheStatus && (
            <span
              className={`status-dot ${
                (cacheStatus.cache?.using_redis || cacheStatus.using_redis)
                  ? "online"
                  : cacheStatus.core_memory?.available
                  ? "online"
                  : "warn"
              }`}
            >
              {(cacheStatus.cache?.using_redis || cacheStatus.using_redis)
                ? "CACHE:REDIS"
                : cacheStatus.core_memory?.available
                ? "CACHE:CORE"
                : "CACHE:LOCAL"}
            </span>
          )}
          {cacheStatus?.core_memory && (
            <span
              className={`status-dot ${cacheStatus.core_memory.available ? "online" : "warn"}`}
            >
              {cacheStatus.core_memory.available ? "MEM:ONLINE" : "MEM:OFFLINE"}
            </span>
          )}
          <span className={`status-dot ${connecting ? "error" : "online"}`}>
            {connecting ? "CORE:OFFLINE" : "CORE:ONLINE"}
          </span>
        </div>
        <button
          className="top-bar-btn"
          onClick={() => setShowModelManager(true)}
          title="Manage models"
        >
          MODELS
        </button>
        <button
          className={`top-bar-btn${hwStatus === "running" ? " top-bar-btn--running" : hardwareOptimised ? " top-bar-btn--done" : ""}`}
          onClick={() => setShowHardwarePanel(true)}
          title="Hardware placement optimisation"
        >
          {hwStatus === "running" ? "HW ···" : hardwareOptimised ? "HW ✓" : "HARDWARE"}
        </button>
        <button
          className="top-bar-btn"
          onClick={() => setShowProfileModal(true)}
          title="User profile"
        >
          PROFILE
        </button>
      </div>

      <div className="main-layout">
        {/* Left Sidebar */}
        <div className="agents-sidebar">
          <div className="sidebar-header">
            <span className="sidebar-title">Agents</span>
            <button
              className="sidebar-add-btn"
              onClick={() => setShowCreateModal(true)}
              title="New agent"
            >
              +
            </button>
          </div>

          <div className="agents-list">
            {agentsLoading ? (
              <div className="loading-agents">
                <div className="loading-indicator">Loading...</div>
              </div>
            ) : validAgents.length === 0 ? (
              <div className="no-agents">
                <span>No agents yet</span>
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="create-first-agent-btn"
                >
                  + Create Agent
                </button>
              </div>
            ) : (
              validAgents.map((agent) => {
                const statusDisplay = getAgentStatusDisplay(
                  agent,
                  thinkingAgents.has(agent.id)
                );
                const avatarColor = getAvatarColor(agent.name);

                return (
                  <div
                    key={agent.id}
                    className={`agent-item ${selectedAgent === agent.id ? "selected" : ""}`}
                    onClick={() => handleAgentSwitch(agent.id)}
                  >
                    <div
                      className="agent-avatar"
                      style={{ backgroundColor: avatarColor }}
                    >
                      {agent.avatar_image ? (
                        agent.avatar_image.startsWith("/api/avatars/") ? (
                          <img
                            src={`${API_BASE}${agent.avatar_image}`}
                            alt={agent.name}
                            className="agent-avatar-image"
                          />
                        ) : (
                          agent.avatar_image
                        )
                      ) : (
                        agent.name.charAt(0).toUpperCase()
                      )}
                      {unreadCounts[agent.id] > 0 && selectedAgent !== agent.id && (
                        <div className="unread-badge">
                          {unreadCounts[agent.id]}
                        </div>
                      )}
                    </div>
                    <div className="agent-info">
                      <div className="agent-name">{agent.name}</div>
                      <div className="agent-meta">
                        <div
                          className={`status-pip ${statusDisplay.class}`}
                          title={statusDisplay.text}
                        />
                        <span className="agent-model-label">
                          {agent.model_name || "no model"}
                          {agent.placement && agent.placement !== "auto" && (
                            <span className={`placement-badge placement-badge--${agent.placement}`}>
                              {agent.placement.toUpperCase()}
                            </span>
                          )}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}

            {/* Create new agent entry */}
            {validAgents.length > 0 && (
              <div
                className="agent-item create-new"
                onClick={() => setShowCreateModal(true)}
              >
                <div className="agent-avatar create-avatar">+</div>
                <div className="agent-info">
                  <div className="agent-name">New Agent</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Chat Main */}
        <div className="chat-main">
          {/* Chat panel header */}
          <div className="chat-header">
            <div className="chat-header-agent">
              {currentAgent ? (
                <>
                  <span className="chat-header-name">{currentAgent.name}</span>
                  <span className="chat-header-sep">—</span>
                  <span className="chat-header-model">
                    {currentAgent.model_name || "no model"}
                  </span>
                </>
              ) : (
                <span className="chat-header-name" style={{ color: "var(--text-muted)" }}>
                  Select an agent
                </span>
              )}
            </div>
            <div className="chat-header-actions">
              {currentAgent && (
                <button
                  className="chat-header-btn"
                  onClick={() => handleEditAgent(currentAgent)}
                  title="Edit agent"
                >
                  Edit
                </button>
              )}
            </div>
          </div>

          {/* Connecting banner */}
          {connecting && (
            <div className="connection-status">
              <div className="connection-message">
                <span className="loading-dots">■</span>
                Connecting to AI service...
              </div>
            </div>
          )}

          {/* Chat Messages */}
          <div
            className={`chat-area ${dragOver ? "drag-over" : ""}`}
            ref={chatAreaRef}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          >
            {messages.length === 0 ? (
              <div className="empty-chat">
                <div className="empty-message">
                  <h3>No messages yet</h3>
                  <p>
                    Type a command below to begin with{" "}
                    {currentAgent?.name || "your agent"}
                  </p>
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <div key={message.id} className="message-wrapper group-start">
                  <div
                    className={`message ${message.sender} ${message.error ? "error" : ""}`}
                  >
                    <div className="message-header">
                      <span
                        className={`message-sender ${message.sender}`}
                      >
                        {message.sender === "user"
                          ? "YOU"
                          : (currentAgent?.name || "AI").toUpperCase()}
                      </span>
                      <span className="message-time">
                        {formatTime(message.timestamp)}
                      </span>
                    </div>

                    {message.isThinking ? (
                      <>
                        <div className="thinking-bar">
                          <div className="thinking-fill" />
                        </div>
                        <div className="thinking-label">Processing...</div>
                      </>
                    ) : message.sender === "ai" && !message.error ? (
                      <div className="message-text message-markdown">
                        <ReactMarkdown>{message.text || ""}</ReactMarkdown>
                      </div>
                    ) : (
                      <div className="message-text">{message.text}</div>
                    )}

                    {message.files && (
                      <div className="message-files">
                        {message.files.map((file, i) => (
                          <span key={i} className="file-tag">
                            {file.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {dragOver && (
              <div className="drop-overlay">
                <div className="drop-message">Drop files to attach</div>
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className="input-area">
            {selectedFiles.length > 0 && (
              <div className="selected-files">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="file-chip">
                    <span>{file.name}</span>
                    <button onClick={() => removeFile(index)}>×</button>
                  </div>
                ))}
              </div>
            )}

            <div className="input-bar">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={
                  connecting
                    ? "Offline..."
                    : `> ${currentAgent?.name || "agent"}...`
                }
                disabled={connecting || thinkingAgents.has(selectedAgent)}
                ref={textareaRef}
                className="message-input"
              />

              <div className="input-actions">
                <button
                  className="file-upload-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={connecting || thinkingAgents.has(selectedAgent)}
                  title="Attach file"
                >
                  [+]
                </button>

                <div className="tools-dropdown">
                  <button
                    className={`tools-btn ${toolsOpen ? "open" : ""}`}
                    onClick={() => setToolsOpen(!toolsOpen)}
                    title="Tools"
                  >
                    CFG
                  </button>
                  {toolsOpen && (
                    <div className="tools-menu">
                      <div className="tools-section">
                        <div className="tools-section-title">Agent</div>
                        {selectedAgent && (
                          <button
                            className="tool-item"
                            onClick={() => handleEditAgent(currentAgent)}
                          >
                            Edit Agent
                          </button>
                        )}
                        <button
                          className="tool-item"
                          onClick={() => {
                            setShowCreateModal(true);
                            setToolsOpen(false);
                          }}
                        >
                          New Agent
                        </button>
                      </div>
                      <div className="tools-section">
                        <div className="tools-section-title">Models</div>
                        <button
                          className="tool-item"
                          onClick={() => {
                            setShowModelManager(true);
                            setToolsOpen(false);
                          }}
                        >
                          Manage Models
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {modelRetryingAgent !== null && modelRetryingAgent === selectedAgent ? (
                  <button
                    className="cancel-model-btn"
                    onClick={() => cancelModelRetry(selectedAgent)}
                    title="Cancel model download"
                  >
                    CANCEL
                  </button>
                ) : (
                  <button
                    className="send-btn"
                    onClick={handleSend}
                    disabled={
                      connecting ||
                      thinkingAgents.has(selectedAgent) ||
                      !inputText.trim()
                    }
                  >
                    {thinkingAgents.has(selectedAgent) ? "..." : "SEND ▶"}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        multiple
        style={{ display: "none" }}
      />

      {/* Modals */}
      <CreateAgentModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onAgentCreated={handleAgentCreated}
        availableDevices={hardwareDevices.map((d) => d.type)}
      />

      <EditAgentModal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setAgentToEdit(null);
        }}
        agent={agentToEdit}
        onAgentUpdated={handleAgentUpdated}
        onAgentDeleted={handleAgentDeleted}
        availableDevices={hardwareDevices.map((d) => d.type)}
      />

      <ModelManager
        isOpen={showModelManager}
        onClose={() => setShowModelManager(false)}
      />

      <UserProfileModal
        isOpen={showProfileModal}
        onClose={() => setShowProfileModal(false)}
      />

      <HardwarePanel
        isOpen={showHardwarePanel}
        onClose={() => setShowHardwarePanel(false)}
        devices={hardwareDevices}
        hwStatus={hwStatus}
        hwSteps={hwSteps}
        hwDevices={hwDevices}
        onStart={handleStartOptimise}
      />
    </div>
  );
}

export default App;
