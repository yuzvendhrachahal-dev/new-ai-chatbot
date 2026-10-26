export interface CustomerLead {
  name: string;
  email: string;
  mobile: string;
  topic_of_interest?: string;
}

export interface MessageItem {
  id: string;
  sender: 'user' | 'assistant' | 'agent' | 'system';
  text: string;
  timestamp: string;
}

export interface ConversationSummary {
  conversation_id: string;
  customer: CustomerLead;
  created_at: string;
  updated_at: string;
  status: 'active' | 'escalated' | 'resolved';
  messages_count: number;
  last_message?: string;
  is_agent_handling: boolean;
}

export interface ConversationDetail {
  conversation_id: string;
  customer: CustomerLead;
  created_at: string;
  updated_at: string;
  status: 'active' | 'escalated' | 'resolved';
  is_agent_handling: boolean;
  messages: MessageItem[];
}
