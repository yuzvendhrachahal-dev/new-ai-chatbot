import React, { useState, useEffect } from 'react';
import { ConversationSummary, ConversationDetail } from '../types';
import { chatApi } from '../api';
import {
  Inbox,
  User,
  Mail,
  Phone,
  Clock,
  Send,
  RefreshCw,
  Tag,
  Key
} from 'lucide-react';

interface AgentDashboardProps {
  initialKey?: string;
}

export const AgentDashboard: React.FC<AgentDashboardProps> = ({ initialKey = 'astro-agent-secret-token' }) => {
  const [agentKey, setAgentKey] = useState(initialKey);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeDetail, setActiveDetail] = useState<ConversationDetail | null>(null);
  const [replyText, setReplyText] = useState('');
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isSendingReply, setIsSendingReply] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const fetchConversations = async () => {
    setIsLoadingList(true);
    setAuthError(null);
    try {
      const data = await chatApi.getAgentConversations(agentKey);
      setConversations(data);
      if (data.length > 0 && !selectedId) {
        setSelectedId(data[0].conversation_id);
      }
    } catch (err: any) {
      setAuthError(err.message || 'Failed to authenticate agent');
    } finally {
      setIsLoadingList(false);
    }
  };

  const fetchDetail = async (id: string) => {
    setIsLoadingDetail(true);
    try {
      const detail = await chatApi.getAgentConversationDetail(id, agentKey);
      setActiveDetail(detail);
    } catch (err: any) {
      console.error(err);
    } finally {
      setIsLoadingDetail(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, []);

  useEffect(() => {
    if (selectedId) {
      fetchDetail(selectedId);
      const interval = setInterval(() => {
        fetchDetail(selectedId);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [selectedId, agentKey]);

  const handleSendReply = async () => {
    if (!selectedId || !replyText.trim() || isSendingReply) return;
    setIsSendingReply(true);
    try {
      await chatApi.sendAgentReply(selectedId, replyText.trim(), agentKey);
      setReplyText('');
      await fetchDetail(selectedId);
      await fetchConversations();
    } catch (err: any) {
      alert(`Error sending reply: ${err.message}`);
    } finally {
      setIsSendingReply(false);
    }
  };

  const handleStatusChange = async (status: string) => {
    if (!selectedId) return;
    try {
      await chatApi.updateConversationStatus(selectedId, status, agentKey);
      await fetchDetail(selectedId);
      await fetchConversations();
    } catch (err: any) {
      alert(`Status update failed: ${err.message}`);
    }
  };

  return (
    <div style={{ width: '100%', maxWidth: '1360px', margin: '0 auto' }}>
      {/* Agent Auth & Subheader Toolbar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'rgba(18, 19, 36, 0.7)',
        padding: '0.8rem 1.25rem',
        borderRadius: '12px',
        marginBottom: '1rem',
        border: '1px solid var(--border-subtle)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Inbox size={20} color="var(--gold-primary)" />
          <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>AstroVed Internal Astrologer Desk</span>
          <span className="session-badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
            Live Feed
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(0,0,0,0.3)', padding: '0.35rem 0.75rem', borderRadius: '8px' }}>
            <Key size={14} color="var(--text-muted)" />
            <input
              type="password"
              placeholder="Internal Agent Key"
              value={agentKey}
              onChange={(e) => setAgentKey(e.target.value)}
              style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '0.8rem', outline: 'none', width: '150px' }}
            />
          </div>
          <button
            onClick={fetchConversations}
            className="view-toggle-btn"
            style={{ padding: '0.4rem 0.8rem' }}
          >
            <RefreshCw size={14} className={isLoadingList ? 'spin-slow' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {authError && (
        <div style={{
          padding: '0.8rem 1.2rem',
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          borderRadius: '8px',
          color: '#fca5a5',
          marginBottom: '1rem',
          fontSize: '0.85rem'
        }}>
          {authError} - Check that your internal agent key matches the backend configuration.
        </div>
      )}

      {/* 3-Column Agent Interface */}
      <div className="agent-dashboard">
        {/* Column 1: Conversations Inbox */}
        <div className="dashboard-panel">
          <div className="panel-header">
            <h3>Seeker Inbox ({conversations.length})</h3>
          </div>
          <div className="inbox-list">
            {conversations.length === 0 ? (
              <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                No active seeker sessions yet.
              </div>
            ) : (
              conversations.map((c) => {
                const isSelected = c.conversation_id === selectedId;
                return (
                  <div
                    key={c.conversation_id}
                    className={`inbox-item ${isSelected ? 'selected' : ''}`}
                    onClick={() => setSelectedId(c.conversation_id)}
                  >
                    <div className="inbox-item-top">
                      <span className="inbox-cust-name">{c.customer.name}</span>
                      <span className="inbox-item-time">
                        {new Date(c.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className="inbox-snippet">{c.last_message || 'Session initiated'}</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className={`inbox-status-tag ${c.status}`}>{c.status}</span>
                      {c.is_agent_handling && (
                        <span style={{ fontSize: '0.65rem', color: 'var(--accent-cyan)' }}>Advisor Active</span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Column 2: Selected Conversation Messages & Live Reply */}
        <div className="agent-chat-center">
          <div className="panel-header">
            <div>
              <h3>
                {activeDetail ? `Session: ${activeDetail.customer.name}` : 'Select a conversation'}
              </h3>
              {activeDetail && (
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  ID: {activeDetail.conversation_id}
                </span>
              )}
            </div>
            {activeDetail && (
              <span className={`inbox-status-tag ${activeDetail.status}`}>
                {activeDetail.status}
              </span>
            )}
          </div>

          <div className="messages-container" style={{ flex: 1 }}>
            {isLoadingDetail ? (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                Loading conversation transcript...
              </div>
            ) : activeDetail?.messages ? (
              activeDetail.messages.map((m) => (
                <div key={m.id} className={`message-row ${m.sender}`}>
                  <div className="message-bubble">
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem', textTransform: 'capitalize' }}>
                      {m.sender === 'user' ? activeDetail.customer.name : m.sender === 'agent' ? 'Astrologer (You)' : 'AstroVed AI'}
                    </div>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
                    <div className="message-time">
                      {new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                Select a seeker conversation from the inbox on the left.
              </div>
            )}
          </div>

          {/* Astrologer Direct Response Controls */}
          {activeDetail && (
            <div className="agent-reply-box">
              <textarea
                placeholder="Type your official Vedic astrological guidance or remedy to the seeker..."
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
              />
              <div className="agent-reply-actions">
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Sending a response places this chat under live human advisor mode.
                </span>
                <button
                  onClick={handleSendReply}
                  disabled={isSendingReply || !replyText.trim()}
                  className="submit-btn"
                  style={{ width: 'auto', padding: '0.55rem 1.25rem', marginTop: 0 }}
                >
                  <Send size={15} />
                  <span>{isSendingReply ? 'Sending...' : 'Send Live Reply'}</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Column 3: Customer Lead Details & Status Actions */}
        <div className="dashboard-panel">
          <div className="panel-header">
            <h3>Seeker Dossier</h3>
          </div>
          {activeDetail ? (
            <div className="cust-detail-body">
              <div className="detail-block">
                <h5>Seeker Name</h5>
                <p style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <User size={15} color="var(--gold-primary)" />
                  {activeDetail.customer.name}
                </p>
              </div>

              <div className="detail-block">
                <h5>Email Address</h5>
                <p style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', wordBreak: 'break-all' }}>
                  <Mail size={15} color="var(--gold-primary)" />
                  {activeDetail.customer.email}
                </p>
              </div>

              <div className="detail-block">
                <h5>Phone / WhatsApp</h5>
                <p style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Phone size={15} color="var(--gold-primary)" />
                  {activeDetail.customer.mobile}
                </p>
              </div>

              <div className="detail-block">
                <h5>Area of Inquiry</h5>
                <p style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-gold)' }}>
                  <Tag size={15} />
                  {activeDetail.customer.topic_of_interest || 'General Astrology'}
                </p>
              </div>

              <div className="detail-block">
                <h5>Session Created</h5>
                <p style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }}>
                  <Clock size={15} color="var(--text-muted)" />
                  {new Date(activeDetail.created_at).toLocaleString()}
                </p>
              </div>

              <hr style={{ borderColor: 'rgba(255,255,255,0.08)', margin: '0.5rem 0' }} />

              <div>
                <h5 style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.6rem' }}>
                  Update Consultation Status
                </h5>
                <div className="status-button-group">
                  <button
                    className={`status-btn ${activeDetail.status === 'active' ? 'active' : ''}`}
                    onClick={() => handleStatusChange('active')}
                  >
                    Active Consultation
                  </button>
                  <button
                    className={`status-btn ${activeDetail.status === 'escalated' ? 'active' : ''}`}
                    onClick={() => handleStatusChange('escalated')}
                  >
                    Escalate to Senior Astrologer
                  </button>
                  <button
                    className={`status-btn ${activeDetail.status === 'resolved' ? 'active' : ''}`}
                    onClick={() => handleStatusChange('resolved')}
                  >
                    Mark as Resolved
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: '2rem 1.25rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Select a conversation to inspect seeker profile details and take triage actions.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
