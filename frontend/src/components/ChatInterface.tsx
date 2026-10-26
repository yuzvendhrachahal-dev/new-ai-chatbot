import React, { useState, useEffect, useRef } from 'react';
import { MessageItem, CustomerLead } from '../types';
import { Send, Sparkles, ShieldCheck } from 'lucide-react';

interface ChatInterfaceProps {
  conversationId: string;
  customer: CustomerLead;
  messages: MessageItem[];
  onSendMessage: (text: string) => void;
  isLoading: boolean;
  isAgentHandling?: boolean;
}

const QUICK_PROMPTS = [
  "How can I strengthen my career according to Vedic Astrology?",
  "What planetary remedy is best for peace of mind?",
  "Tell me about the influence of Saturn and Sade Sati.",
  "Which mantra enhances wealth and abundance?"
];

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  conversationId,
  customer,
  messages,
  onSendMessage,
  isLoading,
  isAgentHandling = false,
}) => {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;
    onSendMessage(inputText.trim());
    setInputText('');
  };

  const handleQuickPrompt = (prompt: string) => {
    if (isLoading) return;
    onSendMessage(prompt);
  };

  return (
    <div className="chat-window">
      {/* Header Banner */}
      <div className="chat-banner">
        <div className="chat-banner-left">
          <div className="chat-avatar-badge">
            🕉️
          </div>
          <div className="chat-banner-info">
            <h4>AstroVed Vedic Guide</h4>
            <div className="chat-banner-status">
              <span className="status-dot"></span>
              <span>{isAgentHandling ? 'Dedicated Astrologer Active' : 'AI Astrological Advisor Online'}</span>
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span className="session-badge">ID: {conversationId.slice(0, 10)}</span>
          <span className="session-badge" style={{ color: 'var(--text-gold)' }}>Seeker: {customer.name}</span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="messages-container">
        {messages.map((msg) => {
          const isAgent = msg.sender === 'agent';

          return (
            <div key={msg.id} className={`message-row ${msg.sender}`}>
              <div className="message-bubble">
                {isAgent && (
                  <div className="agent-tag">
                    <ShieldCheck size={12} style={{ display: 'inline', marginRight: '4px' }} />
                    Live AstroVed Consultant
                  </div>
                )}
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
                <div className="message-time">
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div className="message-row assistant">
            <div className="message-bubble" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sparkles size={16} className="spin-slow" color="#d4af37" />
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Consulting Vedic planetary alignments...
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Topic Chips */}
      <div className="topic-pills-bar">
        {QUICK_PROMPTS.map((prompt, idx) => (
          <button
            key={idx}
            className="topic-pill"
            onClick={() => handleQuickPrompt(prompt)}
            disabled={isLoading}
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Input Message Bar */}
      <form onSubmit={handleSubmit} className="chat-input-bar">
        <input
          type="text"
          className="chat-input-field"
          placeholder="Ask about your planetary dasha, career, health, or remedies..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={isLoading}
        />
        <button
          type="submit"
          className="send-action-btn"
          disabled={isLoading || !inputText.trim()}
          title="Send message"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
};
