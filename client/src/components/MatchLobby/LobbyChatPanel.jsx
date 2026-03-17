import React, { useState, useRef, useEffect } from 'react';

/**
 * LobbyChatPanel — Extracted chat panel for the new MatchLobby (Phase L1).
 *
 * Reuses the same chat logic and styling from WaitingRoom but as a standalone component.
 * Receives chat messages and send callback as props.
 */
export default function LobbyChatPanel({ chat, playerId, onSendChat }) {
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef(null);

  // Auto-scroll chat to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const msg = chatInput.trim();
    if (!msg) return;
    onSendChat(msg);
    setChatInput('');
  };

  return (
    <div className="lobby-chat-panel">
      <h3 className="grim-header grim-header--left grim-header--sm">Communications</h3>
      <div className="lobby-chat-messages">
        {chat.length === 0 && (
          <p className="lobby-chat-placeholder">The war room is quiet... for now.</p>
        )}
        {chat.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.sender_id === playerId ? 'chat-msg-me' : ''}`}>
            <span className="chat-sender">{msg.sender}:</span>
            <span className="chat-text">{msg.message}</span>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>
      <form className="lobby-chat-form" onSubmit={handleSubmit}>
        <input
          type="text"
          className="lobby-chat-input"
          placeholder="Issue orders..."
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          maxLength={500}
        />
        <button type="submit" className="grim-btn grim-btn--sm grim-btn--ember" disabled={!chatInput.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
