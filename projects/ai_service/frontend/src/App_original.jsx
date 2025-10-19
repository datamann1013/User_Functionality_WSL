import React, { useState, useEffect, useRef } from 'react';
import './theme.css';
import { logFrontendError } from './utils/errorLogger';
import CreateAgentModal from './components/CreateAgentModal';
import EditAgentModal from './components/EditAgentModal';
import ModelManager from './components/ModelManager';

// API base URL
const API_BASE =
  process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5000';

// Helper function to generate avatar colors
function getAvatarColor(name) {
  const colors = [
    '#6b46c1',
    '#7c3aed',
    '#8b5cf6',
    '#a855f7',
    '#c084fc',
    '#4c1d95',
    '#5b21b6',
    '#6d28d9',
    '#7c2d12',
    '#92400e',
  ];

  // Safety check: handle undefined, null, or empty names
  if (!name || typeof name !== 'string' || name.length === 0) {
    return colors[0]; // Return first color as default
  }

  const index = name.charCodeAt(0) % colors.length;
  return colors[index];
}

// Helper function to format timestamp
function formatTime(timestamp) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
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

// Helper function to get readable status with download info
function getAgentStatusDisplay(agent) {
  // Check if model is downloading (from metadata)
  let metadata = {};
  try {
    metadata =
      typeof agent.metadata === 'string'
        ? JSON.parse(agent.metadata)
        : agent.metadata || {};
  } catch (e) {
    metadata = {};
  }

  // Always show offline if model is downloading or unavailable
  if (metadata.model_downloading || agent.status === 'offline') {
    return {
      text: 'offline',
      class: 'offline',
    };
  }

  switch (agent.status) {
    case 'idle':
      return {
        text: 'ready',
        class: 'idle',
      };
    case 'busy':
      return {
        text: 'thinking',
        class: 'busy',
      };
    default:
      return {
        text: agent.status,
        class: agent.status,
      };
  }
}

function App() {
  // State management
  const [agents, setAgents] = useState([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [agentToEdit, setAgentToEdit] = useState(null);
  const [showModelManager, setShowModelManager] = useState(false);

  const fileInputRef = useRef(null);
  const chatAreaRef = useRef(null);

  // Load agents from API
  const loadAgents = async () => {
    try {
      setAgentsLoading(true);
      const response = await fetch(`${API_BASE}/api/agents`);
      if (response.ok) {
        const data = await response.json();
        const validAgents = (data.agents || []).filter(
          agent => agent && typeof agent === 'object' && agent.id && agent.name
        );
        setAgents(validAgents);

        // Set first agent as selected if none selected
        if (validAgents.length > 0 && !selectedAgent) {
          await handleAgentSwitch(validAgents[0].id);
        }
      } else {
        // If agents API fails, set empty array to prevent errors
        setAgents([]);
      }
    } catch (error) {
      logFrontendError('AGENTS_LOAD_ERROR', 'Failed to load agents', error);
      setAgents([]); // Set empty array to prevent undefined errors
    } finally {
      setAgentsLoading(false);
    }
  };

  // Load conversation history for an agent
  const loadConversationHistory = async agentId => {
    try {
      const response = await fetch(
        `${API_BASE}/api/agents/${agentId}/conversations?limit=50`
      );
      if (response.ok) {
        const data = await response.json();
        const conversations = data.conversations || [];

        // Convert conversation logs to message format
        const historyMessages = [];
        conversations.forEach(conv => {
          // Add user message
          historyMessages.push({
            id: `${conv.id}-user`,
            sender: 'user',
            text: conv.user_message,
            timestamp: conv.timestamp,
          });

          // Add AI response
          historyMessages.push({
            id: `${conv.id}-ai`,
            sender: 'ai',
            text: conv.ai_response,
            timestamp: conv.timestamp,
            model: conv.model_used,
          });
        });

        setMessages(historyMessages);
        logFrontendError(
          'CONVERSATION_HISTORY_LOADED',
          `Loaded ${conversations.length} conversations for agent ${agentId}`
        );
      }
    } catch (error) {
      logFrontendError(
        'CONVERSATION_HISTORY_ERROR',
        `Failed to load conversation history for agent ${agentId}`,
        error
      );
      setMessages([]); // Clear messages on error
    }
  };

  // Handle agent switching with conversation history loading
  const handleAgentSwitch = async agentId => {
    if (agentId === selectedAgent) return; // No change needed

    setSelectedAgent(agentId);
    setMessages([]); // Clear current messages
    setInputText(''); // Clear input

    // Load conversation history for the selected agent
    if (agentId) {
      await loadConversationHistory(agentId);
    }
  };

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
          'BACKEND_CONNECTION_ERROR',
          'Failed to connect to backend',
          error
        );
        setConnecting(true); // Keep showing connecting state
        setTimeout(checkBackend, 5000); // Retry after 5 seconds
      }
    };

    checkBackend();

    // Set up periodic agent refresh to check for status updates
    const refreshInterval = setInterval(async () => {
      if (!connecting) {
        await loadAgents();
      }
    }, 5000); // Refresh every 5 seconds for better busy status visibility

    return () => clearInterval(refreshInterval);
  }, []);

  // Auto scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // Handle agent creation
  const handleAgentCreated = async newAgent => {
    setAgents(prev => [newAgent, ...prev]);
    await handleAgentSwitch(newAgent.id);
    logFrontendError(
      'FRONTEND_AGENT_CREATED',
      `Created agent: ${newAgent.name}`
    );
  };

  // Handle agent editing
  const handleEditAgent = agent => {
    setAgentToEdit(agent);
    setShowEditModal(true);
    setToolsOpen(false); // Close tools dropdown
  };

  // Handle agent update
  const handleAgentUpdated = updatedAgent => {
    setAgents(prev =>
      prev.map(agent => (agent.id === updatedAgent.id ? updatedAgent : agent))
    );
    logFrontendError(
      'FRONTEND_AGENT_UPDATED',
      `Updated agent: ${updatedAgent.name}`
    );
  };

  // Handle agent deletion
  const handleAgentDeleted = async deletedAgentId => {
    setAgents(prev => prev.filter(agent => agent.id !== deletedAgentId));

    // If deleted agent was selected, select another one
    if (selectedAgent === deletedAgentId) {
      const remainingAgents = agents.filter(
        agent => agent.id !== deletedAgentId
      );
      if (remainingAgents.length > 0) {
        await handleAgentSwitch(remainingAgents[0].id);
      } else {
        setSelectedAgent(null);
        setMessages([]);
      }
    }

    logFrontendError(
      'FRONTEND_AGENT_DELETED',
      `Deleted agent: ${deletedAgentId}`
    );
  };

  // Handle sending messages
  async function handleSend() {
    if (connecting || !inputText.trim() || thinking) return;

    const userMessage = inputText.trim();
    setInputText('');
    setThinking(true);

    // Add user message
    const newMessage = {
      id: Date.now() + Math.random(),
      sender: 'user',
      text: userMessage,
      timestamp: new Date().toISOString(),
      files: selectedFiles.length > 0 ? [...selectedFiles] : undefined,
    };
    setMessages(prev => [...prev, newMessage]);
    setSelectedFiles([]);

    // Add thinking indicator
    const thinkingId = Date.now() + Math.random();
    setMessages(prev => [
      ...prev,
      {
        id: thinkingId,
        sender: 'ai',
        text: 'Thinking...',
        timestamp: new Date().toISOString(),
        isThinking: true,
      },
    ]);

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          agent_id: selectedAgent,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        // Remove thinking message and add AI response
        setMessages(prev => [
          ...prev.filter(msg => msg.id !== thinkingId),
          {
            id: Date.now() + Math.random(),
            sender: 'ai',
            text: data.response,
            timestamp: new Date().toISOString(),
            agentId: selectedAgent,
          },
        ]);
        logFrontendError(
          'FRONTEND_CHAT_SUCCESS',
          'Chat message sent successfully'
        );
      } else {
        const errorData = data;
        let errorMessage = "Sorry, I couldn't process your message. ";

        // Use the improved error messages from the backend
        if (errorData.message) {
          errorMessage = errorData.message;
        } else if (errorData.error) {
          switch (errorData.error) {
            case 'AI service unavailable':
              errorMessage =
                'The AI service is currently offline. Please wait a moment and try again.';
              break;
            case 'AI processing failed':
              errorMessage =
                "I'm having trouble understanding your message. Could you try rephrasing it?";
              break;
            case 'Empty message':
              errorMessage = 'Please type a message to send.';
              break;
            default:
              errorMessage = errorData.error;
          }
        }

        throw new Error(errorMessage);
      }
    } catch (error) {
      // Remove thinking message and show error
      let userFriendlyMessage = 'Sorry, something went wrong. ';

      if (error.message) {
        userFriendlyMessage = error.message;
      } else if (error.name === 'TypeError' || error.name === 'NetworkError') {
        userFriendlyMessage =
          "Can't connect to the AI service. Please check your internet connection and try again.";
      }

      setMessages(prev => [
        ...prev.filter(msg => msg.id !== thinkingId),
        {
          id: Date.now() + Math.random(),
          sender: 'ai',
          text: userFriendlyMessage,
          timestamp: new Date().toISOString(),
          error: true,
        },
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
    <div className='app'>
      {/* Top Bar */}
      <div className='top-bar'>
        <div className='brand'>
          <h2>Rommesmo Informatics</h2>
        </div>
        <div className='top-bar-spacer'></div>
      </div>

      <div className='main-layout'>
        {/* Left Sidebar - Agents */}
        <div className='agents-sidebar'>
          <div className='agents-list'>
            {agentsLoading ? (
              <div className='loading-agents'>
                <div className='loading-indicator'>Loading agents...</div>
              </div>
            ) : agents.length === 0 ? (
              <div className='no-agents'>
                <p>No agents available.</p>
                <button
                  onClick={() => setShowCreateModal(true)}
                  className='create-first-agent-btn'
                >
                  Create your first agent
                </button>
              </div>
            ) : (
              agents
                .filter(agent => agent && agent.id)
                .map(agent => (
                  <div
                    key={agent.id}
                    className={`agent-item ${selectedAgent === agent.id ? 'selected' : ''}`}
                    onClick={() => handleAgentSwitch(agent.id)}
                  >
                    <div
                      className='agent-avatar'
                      style={{
                        backgroundColor: getAvatarColor(
                          agent?.name || 'Unknown'
                        ),
                      }}
                    >
                      {agent.avatar_image ? (
                        agent.avatar_image.startsWith('/api/avatars/') ? (
                          <img
                            src={`http://localhost:5000${agent.avatar_image}`}
                            alt={agent?.name || 'Agent'}
                            className='agent-avatar-image'
                          />
                        ) : (
                          agent.avatar_image
                        )
                      ) : (
                        (agent?.name || 'A').charAt(0).toUpperCase()
                      )}
                    </div>
                    <div className='agent-info'>
                      <div className='agent-name'>
                        {agent?.name || 'Unknown Agent'}
                      </div>
                      <div className='agent-meta'>
                        <span className='downtime'>
                          {calculateDowntime(agent.last_active)}
                        </span>
                        <span
                          className={`status ${getAgentStatusDisplay(agent).class}`}
                        >
                          {getAgentStatusDisplay(agent).text}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
            )}

            {/* Create New Agent Button */}
            <div
              className='agent-item create-new'
              onClick={() => setShowCreateModal(true)}
            >
              <div className='agent-avatar create-avatar'>+</div>
              <div className='agent-info'>
                <div className='agent-name'>Create New Agent</div>
                <div className='agent-meta'>
                  <span className='status'>ready</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className='chat-main'>
          {/* Connection Status */}
          {connecting && (
            <div className='connection-status'>
              <div className='connection-message'>
                <span className='loading-dots'>⚡</span>
                Connecting to AI service...
              </div>
            </div>
          )}

          {/* Chat Messages */}
          <div
            className={`chat-area ${dragOver ? 'drag-over' : ''}`}
            ref={chatAreaRef}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          >
            {messages.length === 0 ? (
              <div className='empty-chat'>
                <div className='empty-message'>
                  <h3>Start a conversation</h3>
                  <p>
                    Type in the input box below to begin chatting with{' '}
                    {agents.find(a => a.id === selectedAgent)?.name ||
                      'your AI assistant'}
                  </p>
                </div>
              </div>
            ) : (
              messages.map(message => (
                <div key={message.id} className='message-wrapper'>
                  <div
                    className={`message ${message.sender} ${message.error ? 'error' : ''} ${message.isThinking ? 'thinking' : ''}`}
                  >
                    <div
                      className='message-avatar'
                      style={{
                        backgroundColor:
                          message.sender === 'user'
                            ? '#6b46c1'
                            : getAvatarColor(
                                agents.find(a => a.id === selectedAgent)
                                  ?.name || 'AI'
                              ),
                      }}
                      title={formatTime(message.timestamp)}
                    >
                      {message.sender === 'user'
                        ? 'U'
                        : agents
                            .find(a => a.id === selectedAgent)
                            ?.name?.charAt(0) || 'A'}
                    </div>
                    <div className='message-content'>
                      <div className='message-text'>{message.text}</div>
                      {message.files && (
                        <div className='message-files'>
                          {message.files.map((file, i) => (
                            <span key={i} className='file-tag'>
                              {file.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className='message-separator'></div>
                </div>
              ))
            )}

            {dragOver && (
              <div className='drop-overlay'>
                <div className='drop-message'>Drop files here to upload</div>
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className='input-area'>
            {selectedFiles.length > 0 && (
              <div className='selected-files'>
                {selectedFiles.map((file, index) => (
                  <div key={index} className='file-chip'>
                    <span>{file.name}</span>
                    <button onClick={() => removeFile(index)}>×</button>
                  </div>
                ))}
              </div>
            )}

            <div className='input-bar'>
              <textarea
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={
                  connecting
                    ? 'Connecting...'
                    : `Message ${agents.find(a => a.id === selectedAgent)?.name || 'AI'}...`
                }
                disabled={connecting || thinking}
                rows={1}
                className='message-input'
              />

              <div className='input-actions'>
                <button
                  className='file-upload-btn'
                  onClick={() => fileInputRef.current?.click()}
                  disabled={connecting || thinking}
                  title='Upload files'
                >
                  📎
                </button>

                <div className='tools-dropdown'>
                  <button
                    className={`tools-btn ${toolsOpen ? 'open' : ''}`}
                    onClick={() => setToolsOpen(!toolsOpen)}
                    disabled={connecting || thinking}
                    title='Agent Management'
                  >
                    ⚙️
                  </button>
                  {toolsOpen && (
                    <div className='tools-menu'>
                      <div className='tools-section'>
                        <div className='tools-section-title'>
                          Agent Management
                        </div>
                        {selectedAgent && (
                          <button
                            className='tool-item'
                            onClick={() =>
                              handleEditAgent(
                                agents.find(a => a.id === selectedAgent)
                              )
                            }
                          >
                            ✏️ Edit Agent
                          </button>
                        )}
                        <button
                          className='tool-item'
                          onClick={() => {
                            setShowCreateModal(true);
                            setToolsOpen(false);
                          }}
                        >
                          ➕ Create Agent
                        </button>
                      </div>

                      <div className='tools-section'>
                        <div className='tools-section-title'>Models</div>
                        <button
                          className='tool-item'
                          onClick={() => {
                            setShowModelManager(true);
                            setToolsOpen(false);
                          }}
                        >
                          📥 Download Models
                        </button>
                        <button className='tool-item'>📊 Model Status</button>
                      </div>
                    </div>
                  )}
                </div>

                <button
                  className='send-btn'
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
        type='file'
        ref={fileInputRef}
        onChange={handleFileSelect}
        multiple
        style={{ display: 'none' }}
      />

      {/* Create Agent Modal */}
      <CreateAgentModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onAgentCreated={handleAgentCreated}
      />

      {/* Edit Agent Modal */}
      <EditAgentModal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setAgentToEdit(null);
        }}
        agent={agentToEdit}
        onAgentUpdated={handleAgentUpdated}
        onAgentDeleted={handleAgentDeleted}
      />

      {/* Model Manager Modal */}
      <ModelManager
        isOpen={showModelManager}
        onClose={() => setShowModelManager(false)}
      />
    </div>
  );
}

export default App;
