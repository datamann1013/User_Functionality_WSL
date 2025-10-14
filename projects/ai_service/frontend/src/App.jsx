import React, { useState, useEffect, useRef } from "react";
import "./theme.css";
import { logFrontendError } from "./utils/errorLogger";

// API base URL
const API_BASE = process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5000';

// Helper function to generate avatar colors
function getAvatarColor(name) {
  const colors = [
    '#6b46c1', '#7c3aed', '#8b5cf6', '#a855f7', '#c084fc',
    '#4c1d95', '#5b21b6', '#6d28d9', '#7c2d12', '#92400e'
  ];
  const index = name.charCodeAt(0) % colors.length;
  return colors[index];
}

// Helper function to format timestamp
function formatTime(timestamp) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit',
    hour12: false 
  });
}

// Helper function to calculate downtime
function calculateDowntime(lastActive) {
  if (!lastActive) return 'Never active';
  const now = new Date();
  const last = new Date(lastActive);
  const diffMs = now - last;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  
  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  if (diffMins > 0) return `${diffMins}m ago`;
  return 'Just now';
}

function App() {
  // State management
  const [agents, setAgents] = useState([
    {
      id: "assistant-1",
      name: "General Assistant",
      status: "idle",
      lastActive: new Date().toISOString(),
      avatar: null
    },
    {
      id: "code-helper",
      name: "Code Helper",
      status: "busy",
      lastActive: new Date(Date.now() - 1800000).toISOString(), // 30 min ago
      avatar: null
    },
    {
      id: "research-bot",
      name: "Research Bot",
      status: "offline",
      lastActive: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
      avatar: null
    }
  ]);
  
  const [selectedAgent, setSelectedAgent] = useState(agents[0].id);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [thinking, setThinking] = useState(false);
  
  const fileInputRef = useRef(null);
  const chatAreaRef = useRef(null);

  // Check backend connection on mount
  useEffect(() => {
    async function checkBackend() {
      try {
        const response = await fetch(`${API_BASE}/health`);
        if (response.ok) {
          setConnecting(false);
          logFrontendError('FRONTEND_INIT', 'Frontend connected to backend successfully');
        } else {
          throw new Error(`Backend responded with status: ${response.status}`);
        }
      } catch (error) {
        setConnecting(true);
        logFrontendError('FRONTEND_CONNECTION_ERROR', 'Failed to connect to backend', error);
      }
    }
    checkBackend();
  }, []);

  // Auto scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // Handle sending messages
  async function handleSend() {
    if (connecting || !inputText.trim() || thinking) return;
    
    const userMessage = inputText.trim();
    setInputText('');
    setThinking(true);
    
    // Add user message
    const newMessage = {
      id: Date.now() + Math.random(),
      sender: "user",
      text: userMessage,
      timestamp: new Date().toISOString(),
      files: selectedFiles.length > 0 ? [...selectedFiles] : undefined
    };
    setMessages(prev => [...prev, newMessage]);
    setSelectedFiles([]);
    
    // Add thinking indicator
    const thinkingId = Date.now() + Math.random();
    setMessages(prev => [...prev, {
      id: thinkingId,
      sender: "ai",
      text: "Thinking...",
      timestamp: new Date().toISOString(),
      isThinking: true
    }]);
    
    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          message: userMessage,
          agent_id: selectedAgent
        }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        // Remove thinking message and add AI response
        setMessages(prev => [
          ...prev.filter(msg => msg.id !== thinkingId),
          {
            id: Date.now() + Math.random(),
            sender: "ai",
            text: data.response,
            timestamp: new Date().toISOString(),
            agentId: selectedAgent
          }
        ]);
        logFrontendError('FRONTEND_CHAT_SUCCESS', 'Chat message sent successfully');
      } else {
        throw new Error(data.error || 'Chat request failed');
      }
    } catch (error) {
      // Remove thinking message and show error
      setMessages(prev => [
        ...prev.filter(msg => msg.id !== thinkingId),
        {
          id: Date.now() + Math.random(),
          sender: "ai",
          text: "Sorry, I couldn't process your message. Please try again.",
          timestamp: new Date().toISOString(),
          error: true
        }
      ]);
      logFrontendError('FRONTEND_CHAT_ERROR', 'Chat request failed', error);
    }
    
    setThinking(false);
  }

  // Handle key press in input
  function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // Handle file selection
  function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    setSelectedFiles(prev => [...prev, ...files]);
  }

  // Handle drag and drop
  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    setSelectedFiles(prev => [...prev, ...files]);
  }

  function handleDragOver(e) {
    e.preventDefault();
    setDragOver(true);
  }

  function handleDragLeave(e) {
    e.preventDefault();
    setDragOver(false);
  }

  // Remove selected file
  function removeFile(index) {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  }

  return (
    <div className="app">
      {/* Top Bar */}
      <div className="top-bar">
        <div className="brand">
          <h2>Rommesmo Informatics</h2>
        </div>
        <div className="top-bar-spacer"></div>
      </div>

      <div className="main-layout">
        {/* Left Sidebar - Agents */}
        <div className="agents-sidebar">
          <div className="agents-list">
            {agents.map(agent => (
              <div 
                key={agent.id}
                className={`agent-item ${selectedAgent === agent.id ? 'selected' : ''}`}
                onClick={() => setSelectedAgent(agent.id)}
              >
                <div 
                  className="agent-avatar"
                  style={{ backgroundColor: getAvatarColor(agent.name) }}
                >
                  {agent.name.charAt(0).toUpperCase()}
                </div>
                <div className="agent-info">
                  <div className="agent-name">{agent.name}</div>
                  <div className="agent-meta">
                    <span className="downtime">
                      {calculateDowntime(agent.lastActive)}
                    </span>
                    <span className={`status ${agent.status}`}>
                      {agent.status}
                    </span>
                  </div>
                </div>
              </div>
            ))}
            
            {/* Create New Agent Button */}
            <div className="agent-item create-new">
              <div className="agent-avatar create-avatar">
                +
              </div>
              <div className="agent-info">
                <div className="agent-name">Create New Agent</div>
                <div className="agent-meta">
                  <span className="status">ready</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="chat-main">
          {/* Chat Messages */}
          <div 
            className={`chat-area ${dragOver ? 'drag-over' : ''}`}
            ref={chatAreaRef}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          >
            {messages.length === 0 ? (
              <div className="empty-chat">
                <div className="empty-message">
                  <h3>Start a conversation</h3>
                  <p>Type in the input box below to begin chatting with {agents.find(a => a.id === selectedAgent)?.name}</p>
                </div>
              </div>
            ) : (
              messages.map(message => (
                <div key={message.id} className="message-wrapper">
                  <div className={`message ${message.sender} ${message.error ? 'error' : ''} ${message.isThinking ? 'thinking' : ''}`}>
                    <div 
                      className="message-avatar"
                      style={{ 
                        backgroundColor: message.sender === 'user' 
                          ? '#6b46c1' 
                          : getAvatarColor(agents.find(a => a.id === selectedAgent)?.name || 'AI')
                      }}
                      title={formatTime(message.timestamp)}
                    >
                      {message.sender === 'user' ? 'U' : agents.find(a => a.id === selectedAgent)?.name?.charAt(0) || 'A'}
                    </div>
                    <div className="message-content">
                      <div className="message-text">{message.text}</div>
                      {message.files && (
                        <div className="message-files">
                          {message.files.map((file, i) => (
                            <span key={i} className="file-tag">{file.name}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="message-separator"></div>
                </div>
              ))
            )}
            
            {dragOver && (
              <div className="drop-overlay">
                <div className="drop-message">
                  Drop files here to upload
                </div>
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
                placeholder={connecting ? "Connecting..." : `Message ${agents.find(a => a.id === selectedAgent)?.name}...`}
                disabled={connecting || thinking}
                rows={1}
                className="message-input"
              />
              
              <div className="input-actions">
                <button 
                  className="file-upload-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={connecting || thinking}
                  title="Upload files"
                >
                  📎
                </button>
                
                <div className="tools-dropdown">
                  <button 
                    className={`tools-btn ${toolsOpen ? 'open' : ''}`}
                    onClick={() => setToolsOpen(!toolsOpen)}
                    disabled={connecting || thinking}
                  >
                    Tools ▼
                  </button>
                  {toolsOpen && (
                    <div className="tools-menu">
                      <div className="tools-empty">No tools available</div>
                    </div>
                  )}
                </div>
                
                <button 
                  className="send-btn"
                  onClick={handleSend}
                  disabled={connecting || thinking || !inputText.trim()}
                >
                  {thinking ? '⏳' : '➤'}
                </button>
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
        style={{ display: 'none' }}
      />
    </div>
  );
}

export default App;
