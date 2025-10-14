import React from 'react';

const InputArea = ({ 
  onSend, 
  thinking, 
  connecting,
  inputText,
  setInputText 
}) => {
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (!inputText.trim() || thinking || connecting) return;
    
    onSend({ 
      text: inputText.trim(),
      type: 'text',
      timestamp: new Date().toISOString()
    });
    
    setInputText('');
  };

  return (
    <div className="input-area">
      <div className="input-container">
        <textarea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={
            connecting 
              ? "Connecting to backend..." 
              : thinking 
                ? "AI is thinking..." 
                : "Type your message..."
          }
          disabled={connecting || thinking}
          rows={1}
          className="message-input"
        />
        
        <div className="input-actions">
          <button 
            onClick={handleSend}
            disabled={connecting || thinking || !inputText.trim()}
            className="send-button"
            title="Send message"
          >
            {thinking ? '⏳' : '➤'}
          </button>
        </div>
      </div>
      
      <div className="input-hints">
        <span className="hint">Press Enter to send • Shift+Enter for new line</span>
      </div>
    </div>
  );
};

export default InputArea;
