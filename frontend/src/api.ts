import { CustomerLead, MessageItem, ConversationSummary, ConversationDetail } from './types';

const API_BASE = '/api';

export const chatApi = {
  // Public Seeker Chat
  async startChat(lead: CustomerLead & { initial_query?: string }): Promise<{
    conversation_id: string;
    welcome_message: string;
    customer: CustomerLead;
  }> {
    const res = await fetch(`${API_BASE}/chat/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(lead),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to start chat' }));
      throw new Error(err.detail || 'Failed to start chat');
    }
    return res.json();
  },

  async sendMessage(conversationId: string, message: string): Promise<{
    conversation_id: string;
    user_message: MessageItem;
    reply: MessageItem;
    is_mock: boolean;
  }> {
    const res = await fetch(`${API_BASE}/chat/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId, message }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to send message' }));
      throw new Error(err.detail || 'Failed to send message');
    }
    return res.json();
  },

  async getMessages(conversationId: string): Promise<{
    conversation_id: string;
    customer_name: string;
    status: string;
    is_agent_handling: boolean;
    messages: MessageItem[];
  }> {
    const res = await fetch(`${API_BASE}/chat/${conversationId}/messages`);
    if (!res.ok) throw new Error('Failed to fetch messages');
    return res.json();
  },

  // Internal Agent Dashboard APIs
  async getAgentConversations(agentKey: string): Promise<ConversationSummary[]> {
    const res = await fetch(`${API_BASE}/agent/conversations`, {
      headers: { 'x-agent-key': agentKey },
    });
    if (!res.ok) throw new Error('Unauthorized or failed to load conversations');
    return res.json();
  },

  async getAgentConversationDetail(conversationId: string, agentKey: string): Promise<ConversationDetail> {
    const res = await fetch(`${API_BASE}/agent/conversations/${conversationId}`, {
      headers: { 'x-agent-key': agentKey },
    });
    if (!res.ok) throw new Error('Failed to fetch conversation details');
    return res.json();
  },

  async sendAgentReply(conversationId: string, reply: string, agentKey: string, agentName = 'AstroVed Astrologer'): Promise<void> {
    const res = await fetch(`${API_BASE}/agent/conversations/${conversationId}/reply`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-agent-key': agentKey,
      },
      body: JSON.stringify({ reply, agent_name: agentName }),
    });
    if (!res.ok) throw new Error('Failed to submit agent reply');
  },

  async updateConversationStatus(conversationId: string, status: string, agentKey: string): Promise<void> {
    const res = await fetch(`${API_BASE}/agent/conversations/${conversationId}/status?status=${status}`, {
      method: 'POST',
      headers: { 'x-agent-key': agentKey },
    });
    if (!res.ok) throw new Error('Failed to update status');
  },

  async checkHealth(): Promise<{ status: string; service: string; openai_configured: boolean }> {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  }
};
