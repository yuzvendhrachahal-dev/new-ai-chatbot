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
  status: string; // 'waiting' | 'with_agent' | 'closed' | 'active' | 'resolved'
  messages_count: number;
  last_message?: string;
  is_agent_handling: boolean;
  assigned_agent?: string | null;
  issue_type?: string;
}

export interface ConversationDetail {
  conversation_id: string;
  customer: CustomerLead;
  created_at: string;
  updated_at: string;
  status: string;
  is_agent_handling: boolean;
  assigned_agent?: string | null;
  issue_type?: string;
  rating?: number;
  feedback?: string;
  messages: MessageItem[];
}

export interface IssueTypeMetric {
  name: string;
  count: number;
  pct: number;
}

export interface StatusMixMetric {
  status: string;
  count: number;
  color: string;
}

export interface RecentUserRecord {
  name: string;
  email: string;
  phone: string;
  status: string;
  issue: string;
  date: string;
}

export interface AnalyticsData {
  total_sessions: number;
  resolved: number;
  waiting: number;
  with_agent: number;
  escalated?: number;
  bot_handled?: number;
  avg_response_time_seconds?: number;
  top_issues: { name: string; count: number; pct: number }[];
  status_mix: { status: string; count: number; color: string }[];
  recent_users: RecentUserRecord[];
}

export interface AgentAuth {
  token: string;
  display_name: string;
}
