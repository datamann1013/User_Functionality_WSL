import React, { useState, useEffect } from "react";

const MainChat = () => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");

  const handleSendMessage = () => {
    if (inputValue.trim()) {
      setMessages([
        ...messages,
        {
          id: Date.now(),
          text: inputValue,
          user: "user",
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
      setInputValue("");
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        backgroundColor: "#36393f",
        color: "white",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px",
          borderBottom: "1px solid #4f545c",
          backgroundColor: "#2f3136",
        }}
      >
        <h2 style={{ margin: 0, color: "#ffffff" }}>AI Chat Service</h2>
      </div>

      {/* Messages Area */}
      <div
        style={{
          flex: 1,
          padding: "16px",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              color: "#b9bbbe",
              marginTop: "40px",
            }}
          >
            Welcome to AI Chat Service! Start a conversation below.
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              style={{
                padding: "12px",
                backgroundColor:
                  message.user === "user" ? "#5865f2" : "#4f545c",
                borderRadius: "8px",
                marginLeft: message.user === "user" ? "20%" : "0",
                marginRight: message.user === "user" ? "0" : "20%",
              }}
            >
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: "bold",
                  marginBottom: "4px",
                }}
              >
                {message.user === "user" ? "You" : "AI Assistant"}
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: "normal",
                    opacity: 0.7,
                    marginLeft: "8px",
                  }}
                >
                  {message.timestamp}
                </span>
              </div>
              <div>{message.text}</div>
            </div>
          ))
        )}
      </div>

      {/* Input Area */}
      <div
        style={{
          padding: "16px",
          borderTop: "1px solid #4f545c",
          backgroundColor: "#2f3136",
        }}
      >
        <div style={{ display: "flex", gap: "12px" }}>
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            style={{
              flex: 1,
              padding: "12px",
              borderRadius: "8px",
              border: "none",
              backgroundColor: "#40444b",
              color: "white",
              resize: "none",
              minHeight: "20px",
              maxHeight: "120px",
              fontFamily: "inherit",
            }}
            rows={1}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim()}
            style={{
              padding: "12px 24px",
              borderRadius: "8px",
              border: "none",
              backgroundColor: inputValue.trim() ? "#5865f2" : "#4f545c",
              color: "white",
              cursor: inputValue.trim() ? "pointer" : "not-allowed",
              fontWeight: "bold",
              transition: "background-color 0.2s",
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default MainChat;
