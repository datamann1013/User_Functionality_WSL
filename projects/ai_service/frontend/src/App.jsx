import React, { useState, useEffect } from "react";
import "./theme.css";
import { logFrontendError } from "./utils/errorLogger";

// API base URL
const API_BASE = process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5000';

function App() {
  const [messages, setMessages] = useState([]);
  const [connecting, setConnecting] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [inputText, setInputText] = useState('');

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

  async function handleSend() {
    if (connecting || !inputText.trim() || thinking) return;
    
    const userMessage = inputText.trim();
    setInputText('');
    setThinking(true);
    
    // Add user message
    setMessages(prev => [...prev, { 
      id: Date.now() + Math.random(), 
      sender: "user", 
      text: userMessage 
    }]);
    
    // Add thinking indicator
    const thinkingId = Date.now() + Math.random();
    setMessages(prev => [...prev, { 
      id: thinkingId, 
      sender: "ai", 
      text: "🤔 Thinking..." 
    }]);
    
    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        // Remove thinking message and add AI response
        setMessages(prev => [
          ...prev.filter(msg => msg.id !== thinkingId),
          { 
            id: Date.now() + Math.random(), 
            sender: "ai", 
            text: data.response 
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
          text: "❌ Sorry, I couldn't process your message. Please try again." 
        }
      ]);
      logFrontendError('FRONTEND_CHAT_ERROR', 'Chat request failed', error);
    }
    
    setThinking(false);
  }

  function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="app">
      <div className="header">
        <h1>🤖 AI Service</h1>
        <div className={`status ${connecting ? 'disconnected' : 'connected'}`}>
          {connecting ? '❌ Disconnected' : '✅ Connected'}
        </div>
      </div>
      
      <div className="chat-container">
        <div className="messages">
          {messages.length === 0 && (
            <div className="welcome-message">
              <h2>Welcome to the AI Service!</h2>
              <p>This is a simple prototype. Start chatting below.</p>
            </div>
          )}
          
          {messages.map(msg => (
            <div key={msg.id} className={`message ${msg.sender}`}>
              <div className="message-content">
                {msg.text}
              </div>
            </div>
          ))}
        </div>
        
        <div className="input-area">
          <div className="input-container">
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={connecting ? "Connecting to backend..." : "Type your message..."}
              disabled={connecting || thinking}
              rows={1}
            />
            <button 
              onClick={handleSend}
              disabled={connecting || thinking || !inputText.trim()}
              className="send-button"
            >
              {thinking ? '⏳' : '➤'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
