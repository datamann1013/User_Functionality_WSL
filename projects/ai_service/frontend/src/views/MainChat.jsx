import React from 'react';
import ChatBox from '../componens/ChatBox';
import InputArea from '../componens/InputArea';

const MainChat = ({ 
  messages, 
  thinking, 
  connecting, 
  onSend,
  inputText,
  setInputText 
}) => {
  return (
    <div className="main-chat">
      <div className="chat-header">
        <h2>AI Chat</h2>
        <div className={`connection-status ${connecting ? 'disconnected' : 'connected'}`}>
          {connecting ? '❌ Disconnected' : '✅ Connected'}
        </div>
      </div>
      
      <ChatBox 
        messages={messages}
        thinking={thinking}
      />
      
      <InputArea 
        onSend={onSend}
        thinking={thinking}
        connecting={connecting}
        inputText={inputText}
        setInputText={setInputText}
      />
    </div>
  );
};

export default MainChat;
