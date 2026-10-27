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
    reply?: MessageItem | null;
    is_mock: boolean;
    sources?: any[];
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
    assigned_agent?: string | null;
    issue_type?: string;
    rating?: number;
    feedback?: string;
    messages: MessageItem[];
  }> {
    let attempts = 0;
    const maxAttempts = 3;
    while (attempts < maxAttempts) {
      attempts++;
      try {
        const res = await fetch(`${API_BASE}/chat/${conversationId}/messages`);
        if (res.status === 404) {
          const err: any = new Error('Session not found');
          err.status = 404;
          throw err;
        }
        if (!res.ok) {
          if (res.status >= 500 && attempts < maxAttempts) {
            await new Promise(r => setTimeout(r, 600 * attempts));
            continue;
          }
          throw new Error('Failed to fetch messages');
        }
        return await res.json();
      } catch (err: any) {
        if (err.status === 404) throw err;
        if (attempts >= maxAttempts) throw err;
        await new Promise(r => setTimeout(r, 600 * attempts));
      }
    }
    throw new Error('Failed to fetch messages after retries');
  },

  async handoff(conversationId: string, issueType?: string): Promise<{ status: string; message: MessageItem }> {
    const params = issueType ? `?issue_type=${encodeURIComponent(issueType)}` : '';
    const res = await fetch(`${API_BASE}/chat/${conversationId}/handoff${params}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ issue_type: issueType })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to request handoff' }));
      throw new Error(err.detail || 'Failed to request handoff');
    }
    return res.json();
  },

  async endChat(conversationId: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/chat/${conversationId}/end`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to end chat');
    return res.json();
  },

  async submitRating(conversationId: string, rating: number, feedback?: string): Promise<{
    status: string;
    conversation_id: string;
    rating: number;
    feedback?: string;
    already_submitted: boolean;
    message: string;
  }> {
    const res = await fetch(`${API_BASE}/chat/${conversationId}/rating`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating, feedback }),
    });
    if (!res.ok) throw new Error('Failed to submit rating');
    return res.json();
  },

  // Internal Agent Dashboard APIs
  async agentLogin(username: string, password: string): Promise<{ success: boolean; token: string; display_name: string; role?: string }> {
    const res = await fetch(`${API_BASE}/agent/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Invalid credentials' }));
      throw new Error(err.detail || 'Invalid credentials');
    }
    return res.json();
  },

  async getAgentConversations(token: string, tab = 'all', search?: string): Promise<ConversationSummary[]> {
    const params = new URLSearchParams({ tab });
    if (search) params.append('search', search);

    const res = await fetch(`${API_BASE}/agent/conversations?${params.toString()}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'x-agent-key': token
      },
    });
    if (!res.ok) throw new Error('Unauthorized or failed to load conversations');
    return res.json();
  },

  async getAgentConversationDetail(conversationId: string, token: string): Promise<ConversationDetail> {
    const res = await fetch(`${API_BASE}/agent/conversations/${conversationId}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'x-agent-key': token
      },
    });
    if (!res.ok) throw new Error('Failed to fetch conversation details');
    return res.json();
  },

  async claimChat(conversationId: string, agentName: string, token: string): Promise<void> {
    const res = await fetch(`${API_BASE}/agent/conversations/${conversationId}/claim`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'x-agent-key': token
      },
      body: JSON.stringify({ agent_name: agentName })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to claim chat' }));
      throw new Error(err.detail || 'Failed to claim chat');
    }
  },

  async sendAgentReply(conversationId: string, reply: string, token: string, agentName = 'AstroVed Astrologer'): Promise<void> {
    const res = await fetch(`${API_BASE}/agent/conversations/${conversationId}/reply`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'x-agent-key': token,
      },
      body: JSON.stringify({ reply, agent_name: agentName }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to submit agent reply' }));
      throw new Error(err.detail || 'Failed to submit agent reply');
    }
  },

  async returnToBot(conversationId: string, token: string): Promise<void> {
    const res = await fetch(`${API_BASE}/agent/conversations/${conversationId}/return-to-bot`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'x-agent-key': token
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to return session to bot' }));
      throw new Error(err.detail || 'Failed to return session to bot');
    }
  },

  async closeChat(conversationId: string, token: string): Promise<void> {
    const res = await fetch(`${API_BASE}/agent/conversations/${conversationId}/close`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'x-agent-key': token
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to close conversation' }));
      throw new Error(err.detail || 'Failed to close conversation');
    }
  },

  async updateConversationStatus(conversationId: string, status: string, token: string): Promise<void> {
    const res = await fetch(`${API_BASE}/agent/conversations/${conversationId}/status?status=${status}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'x-agent-key': token
      },
    });
    if (!res.ok) throw new Error('Failed to update status');
  },

  async getAnalytics(token: string): Promise<any> {
    const res = await fetch(`${API_BASE}/agent/analytics`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'x-agent-key': token
      },
    });
    if (!res.ok) throw new Error('Failed to load analytics');
    return res.json();
  },

  async checkHealth(): Promise<{ status: string; service: string; database?: any; openai_configured: boolean }> {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  }
};
