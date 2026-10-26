import React, { useState } from 'react';
import { WelcomeForm } from './components/WelcomeForm';
import { ChatInterface } from './components/ChatInterface';
import { AgentDashboard } from './components/AgentDashboard';
import { CustomerLead, MessageItem } from './types';
import { chatApi } from './api';
import { MessageSquare, LayoutDashboard } from 'lucide-react';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<'seeker' | 'agent'>('seeker');
  
  // Public Seeker State
  const [customer, setCustomer] = useState<CustomerLead | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [isStartingChat, setIsStartingChat] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [isAgentHandling, setIsAgentHandling] = useState(false);

  const handleStartChat = async (lead: CustomerLead & { initial_query?: string }) => {
    setIsStartingChat(true);
    try {
      const response = await chatApi.startChat(lead);
      setCustomer(response.customer);
      setConversationId(response.conversation_id);
      
      const initialMsgs: MessageItem[] = [
        {
          id: 'welcome-1',
          sender: 'assistant',
          text: response.welcome_message,
          timestamp: new Date().toISOString(),
        },
      ];

      if (lead.initial_query) {
        initialMsgs.push({
          id: 'initial-query',
          sender: 'user',
          text: lead.initial_query,
          timestamp: new Date().toISOString(),
        });
      }

      setMessages(initialMsgs);

      // If user provided initial query, send it to receive AI reply
      if (lead.initial_query) {
        try {
          const replyRes = await chatApi.sendMessage(response.conversation_id, lead.initial_query);
          setMessages((prev) => [...prev, replyRes.reply]);
        } catch (err) {
          console.error('Error fetching initial reply:', err);
        }
      }
    } catch (err: any) {
      alert(`Could not start chat: ${err.message}`);
    } finally {
      setIsStartingChat(false);
    }
  };

  const handleSendMessage = async (text: string) => {
    if (!conversationId) return;

    // Optimistic user message addition
    const tempUserMsg: MessageItem = {
      id: `tmp-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setIsSendingMessage(true);

    try {
      const res = await chatApi.sendMessage(conversationId, text);
      // Replace with official response
      setMessages((prev) => [...prev, res.reply]);
      if (res.reply.sender === 'agent') {
        setIsAgentHandling(true);
      }
    } catch (err: any) {
      alert(`Failed to send message: ${err.message}`);
    } finally {
      setIsSendingMessage(false);
    }
  };

  const resetSeekerSession = () => {
    setCustomer(null);
    setConversationId(null);
    setMessages([]);
    setIsAgentHandling(false);
  };

  return (
    <div>
      {/* Top Navigation Bar */}
      <header className="app-header">
        <div className="brand-wrapper">
          <div className="brand-logo-badge">🕉️</div>
          <div>
            <div className="brand-title">AstroVed AI</div>
            <div className="brand-subtitle">Vedic Astrology & Remedial Intelligence</div>
          </div>
        </div>

        <nav className="nav-actions">
          <button
            className={`view-toggle-btn ${currentView === 'seeker' ? 'active' : ''}`}
            onClick={() => setCurrentView('seeker')}
          >
            <MessageSquare size={16} />
            <span>Customer Chat</span>
          </button>

          <button
            className={`view-toggle-btn ${currentView === 'agent' ? 'active' : ''}`}
            onClick={() => setCurrentView('agent')}
          >
            <LayoutDashboard size={16} />
            <span>Internal Agent Desk</span>
          </button>

          {currentView === 'seeker' && conversationId && (
            <button
              onClick={resetSeekerSession}
              className="view-toggle-btn"
              style={{ fontSize: '0.75rem', borderColor: 'rgba(255,255,255,0.1)' }}
            >
              New Seeker
            </button>
          )}
        </nav>
      </header>

      {/* Main Body Content */}
      <main className="main-container">
        {currentView === 'seeker' ? (
          customer && conversationId ? (
            <ChatInterface
              conversationId={conversationId}
              customer={customer}
              messages={messages}
              onSendMessage={handleSendMessage}
              isLoading={isSendingMessage}
              isAgentHandling={isAgentHandling}
            />
          ) : (
            <WelcomeForm onSubmit={handleStartChat} isLoading={isStartingChat} />
          )
        ) : (
          <AgentDashboard />
        )}
      </main>
    </div>
  );
};

export default App;
