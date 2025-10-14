import React from 'react';

const ChatBox = ({ messages, thinking }) => {
  const renderMessage = (message) => {
    const isUser = message.sender === 'user';
    
    return (
      <div key={message.id} className={`message ${message.sender}`}>
        <div className="message-content">
          <div className="message-text">
            {message.text}
          </div>
          {message.timestamp && (
            <div className="message-timestamp">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="chat-box">
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <h2>🤖 Welcome to AI Service</h2>
            <p>Start a conversation by typing a message below.</p>
          </div>
        )}
        
        {messages.map(renderMessage)}
        
        {thinking && (
          <div className="message ai thinking">
            <div className="message-content">
              <div className="message-text">
                <span className="thinking-dots">🤔 Thinking</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatBox;
