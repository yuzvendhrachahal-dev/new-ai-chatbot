import React, { useState, useEffect, useRef } from 'react';
import { ConversationSummary, ConversationDetail, AnalyticsData } from '../types';
import { chatApi } from '../api';
import { ASTROVED_LOGO } from '../assets/logo';
import { MessageRenderer } from './MessageRenderer';
import '../styles/agent-dashboard.css';

interface AgentDashboardProps {
  onSwitchToCustomer?: () => void;
}

type TabType = 'all' | 'my' | 'waiting' | 'with_agent' | 'closed';
type RightPanelTab = 'user' | 'activity' | 'quick';

const QUICK_REPLIES = [
  "Namaste! Thank you for reaching out to AstroVed. How can I assist you today?",
  "I am reviewing your birth chart and planetary dasha details now. Please hold on a moment.",
  "Your request has been noted. Our Vedic astrology team will guide you through the remedies.",
  "Could you please confirm your date, exact time, and city of birth for accuracy?",
  "I understand your concern. Let me consult the planetary alignment for your query.",
  "Are there any specific planetary transits or Sade Sati queries you would like to ask about?",
  "Your consultation remedies have been noted. May cosmic blessings be upon you! ✨"
];

export const AgentDashboard: React.FC<AgentDashboardProps> = () => {
  // Authentication state
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [agentToken, setAgentToken] = useState('');
  const [agentName, setAgentName] = useState('');

  // Main console state
  const [allSessions, setAllSessions] = useState<ConversationSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeDetail, setActiveDetail] = useState<ConversationDetail | null>(null);
  const [currentTab, setCurrentTab] = useState<TabType>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [rightPanelTab, setRightPanelTab] = useState<RightPanelTab>('user');
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [replyInput, setReplyInput] = useState('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);

  const chatBodyRef = useRef<HTMLDivElement | null>(null);
  const composerInputRef = useRef<HTMLInputElement | null>(null);
  const isAgentAtBottomRef = useRef<boolean>(true);
  const [showAgentJump, setShowAgentJump] = useState<boolean>(false);
  const prevAgentMsgCountRef = useRef<number>(0);

  const handleAgentScroll = () => {
    const el = chatBodyRef.current;
    if (!el) return;
    const threshold = 70;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const isBottom = distanceFromBottom <= threshold;
    isAgentAtBottomRef.current = isBottom;
    if (isBottom) {
      setShowAgentJump(false);
    }
  };

  const handleAgentJumpToLatest = () => {
    if (chatBodyRef.current) {
      chatBodyRef.current.scrollTo({ top: chatBodyRef.current.scrollHeight, behavior: 'smooth' });
      setShowAgentJump(false);
      isAgentAtBottomRef.current = true;
    }
  };

  // Push notifications
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission>(() => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      return Notification.permission;
    }
    return 'default';
  });
  const [pushEnabled, setPushEnabled] = useState<boolean>(() => {
    return localStorage.getItem('av_push_enabled') !== 'false';
  });
  const prevWaitingCountRef = useRef<number>(0);

  // Check session storage on mount
  useEffect(() => {
    const savedAgent = sessionStorage.getItem('av_ag');
    const savedToken = sessionStorage.getItem('av_token');
    if (savedAgent && savedToken) {
      setAgentName(savedAgent);
      setAgentToken(savedToken);
      setIsLoggedIn(true);
    }
  }, []);

  const showToast = (msg: string, duration = 3000) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), duration);
  };

  const copyToClipboard = (text: string, label: string) => {
    if (!text) return;
    navigator.clipboard?.writeText(text).then(() => {
      showToast(`Copied ${label} to clipboard!`);
    }).catch(() => {
      showToast(text);
    });
  };

  const handleTogglePushNotifications = async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      showToast('Push notifications are not supported in this browser.');
      return;
    }

    if (Notification.permission === 'granted') {
      const next = !pushEnabled;
      setPushEnabled(next);
      localStorage.setItem('av_push_enabled', String(next));
      showToast(next ? '🔔 Push notifications enabled!' : '🔕 Push notifications muted.');
    } else if (Notification.permission === 'denied') {
      showToast('Notifications are blocked. Please enable them in browser site settings.');
    } else {
      try {
        const permission = await Notification.requestPermission();
        setNotificationPermission(permission);
        if (permission === 'granted') {
          setPushEnabled(true);
          localStorage.setItem('av_push_enabled', 'true');
          showToast('🔔 Push notifications allowed successfully!');
          try {
            new Notification('AstroVed Advisor Support', {
              body: 'Desktop notifications are active. You will be alerted for incoming customer chats.',
              icon: ASTROVED_LOGO
            });
          } catch {}
        } else {
          showToast('Notifications blocked.');
        }
      } catch {
        showToast('Notification request cancelled.');
      }
    }
  };

  // Fetch all sessions from backend
  const fetchSessions = async () => {
    if (!agentToken) return;
    try {
      const data = await chatApi.getAgentConversations(agentToken);
      if (Array.isArray(data)) {
        setAllSessions(data);
        const currentWaiting = data.filter(s => s.status === 'waiting').length;
        if (
          pushEnabled &&
          typeof window !== 'undefined' &&
          'Notification' in window &&
          Notification.permission === 'granted' &&
          currentWaiting > prevWaitingCountRef.current
        ) {
          try {
            new Notification('✦ New Seeker in Waiting Queue!', {
              body: `${currentWaiting} chat(s) currently waiting for astrology assistance.`,
              icon: ASTROVED_LOGO
            });
          } catch {}
        }
        prevWaitingCountRef.current = currentWaiting;
      }
    } catch {
      // Keep existing sessions if network blips
    }
  };

  // Fetch detail for selected conversation
  const fetchDetail = async (id: string) => {
    if (!agentToken) return;
    setIsLoadingDetail(true);
    try {
      const detail = await chatApi.getAgentConversationDetail(id, agentToken);
      setActiveDetail(detail);
    } catch {
      // fallback
    } finally {
      setIsLoadingDetail(false);
    }
  };

  // Fetch analytics
  const fetchAnalytics = async () => {
    if (!agentToken) return;
    try {
      const data = await chatApi.getAnalytics(agentToken);
      setAnalyticsData(data);
    } catch {}
  };

  // Poll sessions periodically when logged in
  useEffect(() => {
    if (isLoggedIn) {
      fetchSessions();
      const interval = setInterval(fetchSessions, 4000);
      return () => clearInterval(interval);
    }
  }, [isLoggedIn, agentToken]);

  // Poll detail when a session is active
  useEffect(() => {
    if (isLoggedIn && activeSessionId) {
      fetchDetail(activeSessionId);
      const interval = setInterval(() => fetchDetail(activeSessionId), 3500);
      return () => clearInterval(interval);
    }
  }, [isLoggedIn, activeSessionId, agentToken]);

  // Real-time SSE stream for agent live queue and incoming messages
  useEffect(() => {
    if (!isLoggedIn || !agentToken) return;

    const es = new EventSource(`/api/agent/events?token=${encodeURIComponent(agentToken)}`);

    es.addEventListener('queue_update', (e: MessageEvent) => {
      fetchSessions();
      try {
        const payload = JSON.parse(e.data);
        if (payload?.action === 'waiting') {
          showToast(`🔔 Customer waiting for advisor (${payload.waiting_count || 1} in queue)`);
          if (
            pushEnabled &&
            typeof window !== 'undefined' &&
            'Notification' in window &&
            Notification.permission === 'granted'
          ) {
            try {
              new Notification('✦ New Customer in Waiting Queue!', {
                body: `${payload.waiting_count || 1} consultation(s) waiting for an AstroVed advisor.`,
                icon: ASTROVED_LOGO
              });
            } catch {}
          }
        }
      } catch {}
    });

    es.addEventListener('message', (e: MessageEvent) => {
      try {
        const payload = JSON.parse(e.data);
        if (activeSessionId && payload?.conversation_id === activeSessionId) {
          fetchDetail(activeSessionId);
        }
      } catch {}
    });

    es.addEventListener('status_change', (e: MessageEvent) => {
      try {
        const payload = JSON.parse(e.data);
        if (activeSessionId && payload?.conversation_id === activeSessionId) {
          fetchDetail(activeSessionId);
        }
        fetchSessions();
      } catch {}
    });

    return () => {
      es.close();
    };
  }, [isLoggedIn, agentToken, activeSessionId]);

  // Smart scroll messages to bottom on detail update: preserve scroll if agent is reading older history
  useEffect(() => {
    const currentCount = activeDetail?.messages?.length || 0;
    const prevCount = prevAgentMsgCountRef.current;
    const hasNewMessages = currentCount > prevCount;
    prevAgentMsgCountRef.current = currentCount;

    if (chatBodyRef.current) {
      if (prevCount === 0 || isAgentAtBottomRef.current) {
        chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
        setShowAgentJump(false);
      } else if (hasNewMessages) {
        setShowAgentJump(true);
      }
    }
  }, [activeDetail]);

  const handleLogin = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setLoginError(null);

    try {
      const res = await chatApi.agentLogin(username, password);
      if (res && res.success) {
        setAgentToken(res.token);
        setAgentName(res.display_name);
        sessionStorage.setItem('av_ag', res.display_name);
        sessionStorage.setItem('av_token', res.token);
        setIsLoggedIn(true);
        showToast(`Welcome back, ${res.display_name}! ✨`);

        if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'default') {
          Notification.requestPermission().then(perm => {
            setNotificationPermission(perm);
            if (perm === 'granted') {
              setPushEnabled(true);
              localStorage.setItem('av_push_enabled', 'true');
            }
          });
        }
      } else {
        setLoginError('Invalid credentials — please try again');
      }
    } catch (err: any) {
      setLoginError(err?.message || 'Invalid credentials — please try again');
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem('av_ag');
    sessionStorage.removeItem('av_token');
    setIsLoggedIn(false);
    setActiveSessionId(null);
    setActiveDetail(null);
    setShowAnalytics(false);
  };

  const handleClaim = async () => {
    if (!activeSessionId || !agentToken) return;
    try {
      setActiveDetail(prev => prev ? {
        ...prev,
        status: 'active',
        assigned_agent: agentName,
        is_agent_handling: true
      } : prev);

      await chatApi.claimChat(activeSessionId, agentName, agentToken);
      showToast('Consultation claimed successfully! 🤝');
      await fetchDetail(activeSessionId);
      await fetchSessions();
      composerInputRef.current?.focus();
    } catch (err: any) {
      showToast(err.message || 'Could not claim chat (already claimed or unavailable)');
      await fetchSessions();
      await fetchDetail(activeSessionId);
    }
  };

  const handleReturnToBot = async () => {
    if (!activeSessionId || !agentToken) return;
    try {
      setActiveDetail(prev => prev ? {
        ...prev,
        status: 'bot_active',
        assigned_agent: null,
        is_agent_handling: false
      } : prev);

      await chatApi.returnToBot(activeSessionId, agentToken);
      showToast('Returned session to AstroVed AI Guide. Advisor assignment cleared.');
      await fetchDetail(activeSessionId);
      await fetchSessions();
    } catch (err: any) {
      showToast(err.message || 'Failed to return session to bot');
      await fetchDetail(activeSessionId);
      await fetchSessions();
    }
  };

  const handleSendReply = async () => {
    const text = replyInput.trim();
    if (!text || !activeSessionId || !agentToken) return;

    setReplyInput('');
    try {
      await chatApi.sendAgentReply(activeSessionId, text, agentToken, agentName);
      await fetchDetail(activeSessionId);
      await fetchSessions();
    } catch (err: any) {
      showToast(err.message || 'Failed to send reply');
    }
  };

  const handleUseQuickReply = (text: string) => {
    setReplyInput(text);
    composerInputRef.current?.focus();
  };

  // Filtered session list
  const filteredSessions = allSessions.filter(s => {
    if (currentTab === 'my') {
      const isAssignedToMe = (s.assigned_agent || '').toLowerCase() === (agentName || '').toLowerCase();
      if (!isAssignedToMe) return false;
    } else if (currentTab === 'waiting') {
      if (s.status !== 'waiting') return false;
    } else if (currentTab === 'with_agent') {
      if (s.status !== 'with_agent' && s.status !== 'active') return false;
    } else if (currentTab === 'closed') {
      if (s.status !== 'closed' && s.status !== 'resolved') return false;
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = (s.customer?.name || '').toLowerCase().includes(q);
      const matchEmail = (s.customer?.email || '').toLowerCase().includes(q);
      const matchPhone = (s.customer?.mobile || '').toLowerCase().includes(q);
      const matchId = (s.conversation_id || '').toLowerCase().includes(q);
      const matchTopic = (s.issue_type || '').toLowerCase().includes(q);
      return matchName || matchEmail || matchPhone || matchId || matchTopic;
    }
    return true;
  });

  const waitingCount = allSessions.filter(s => s.status === 'waiting').length;
  const withAgentCount = allSessions.filter(
    s => (s.status === 'with_agent' || s.status === 'active') && s.is_agent_handling
  ).length;
  const myConversationsCount = allSessions.filter(
    s => (s.assigned_agent || '').toLowerCase() === (agentName || '').toLowerCase() && s.status !== 'closed'
  ).length;

  const formatWaitTime = (dateStr?: string): string => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);
      if (diffSec < 60) return 'Just now';
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHour = Math.floor(diffMin / 60);
      if (diffHour < 24) return `${diffHour}h ago`;
      const diffDay = Math.floor(diffHour / 24);
      if (diffDay < 7) return `${diffDay}d ago`;
      return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
    } catch {
      return '';
    }
  };

  const formatTimeHM = (dateStr?: string): string => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch {
      return '';
    }
  };

  return (
    <div className="agent-console-root">
      {/* ── 1. LOGIN SCREEN ── */}
      {!isLoggedIn ? (
        <div className="login-screen-wrapper">
          <div className="login-card">
            <div className="login-logo-orb">
              <img src={ASTROVED_LOGO} alt="AstroVed" />
            </div>
            <h2 className="login-title">AstroVed</h2>
            <div className="login-subtitle">Support Console</div>

            <form onSubmit={handleLogin}>
              <div className="login-field-group">
                <label htmlFor="agent-username">Username</label>
                <input
                  id="agent-username"
                  type="text"
                  placeholder="agent1"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  autoComplete="username"
                  required
                />
              </div>

              <div className="login-field-group">
                <label htmlFor="agent-password">Password</label>
                <div className="login-pass-wrap">
                  <input
                    id="agent-password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    autoComplete="current-password"
                    required
                  />
                  <button
                    type="button"
                    className="login-pass-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label="Toggle password visibility"
                    title="Toggle password visibility"
                  >
                    {!showPassword ? (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                      </svg>
                    ) : (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                        <line x1="1" y1="1" x2="23" y2="23"></line>
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <button className="login-submit-btn" type="submit">
                Sign In to Console
              </button>
            </form>

            {loginError && (
              <div className="login-error-alert">
                {loginError}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ── 2. APP CONSOLE (Intercom / Zendesk 3-Panel Layout) ── */
        <div className="console-app-container">
          {/* ── LEFT NAVIGATION RAIL ── */}
          <nav className="nav-rail" aria-label="Support workspace navigation">
            <div className="nav-rail-brand" title="AstroVed Support Console">
              <img className="nav-rail-logo" src={ASTROVED_LOGO} alt="AstroVed" />
            </div>

            <div className="nav-rail-items">
              <button
                className={`rail-item-btn ${currentTab === 'all' ? 'active' : ''}`}
                onClick={() => setCurrentTab('all')}
                title="Inbox (All Conversations)"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline>
                  <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path>
                </svg>
              </button>

              <button
                className={`rail-item-btn ${currentTab === 'my' ? 'active' : ''}`}
                onClick={() => setCurrentTab('my')}
                title="My Conversations (Assigned to Me)"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
                {myConversationsCount > 0 && (
                  <span className="rail-badge active">{myConversationsCount}</span>
                )}
              </button>

              <button
                className={`rail-item-btn ${currentTab === 'waiting' ? 'active' : ''}`}
                onClick={() => setCurrentTab('waiting')}
                title="Waiting Queue (Need Advisor)"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                {waitingCount > 0 && (
                  <span className="rail-badge waiting">{waitingCount}</span>
                )}
              </button>

              <button
                className={`rail-item-btn ${currentTab === 'with_agent' ? 'active' : ''}`}
                onClick={() => setCurrentTab('with_agent')}
                title="Active Conversations (With Agent)"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                {withAgentCount > 0 && (
                  <span className="rail-badge active">{withAgentCount}</span>
                )}
              </button>

              <button
                className={`rail-item-btn ${currentTab === 'closed' ? 'active' : ''}`}
                onClick={() => setCurrentTab('closed')}
                title="History & Resolved"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
              </button>

              <div className="rail-divider"></div>

              <button
                className="rail-item-btn"
                onClick={() => {
                  setShowAnalytics(!showAnalytics);
                  if (!showAnalytics) fetchAnalytics();
                }}
                title="Command Analytics"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="20" x2="18" y2="10"></line>
                  <line x1="12" y1="20" x2="12" y2="4"></line>
                  <line x1="6" y1="20" x2="6" y2="14"></line>
                </svg>
              </button>

              <button
                className={`rail-item-btn ${notificationPermission === 'granted' && pushEnabled ? 'active' : ''}`}
                onClick={handleTogglePushNotifications}
                title={
                  notificationPermission === 'granted'
                    ? pushEnabled
                      ? 'Push Alerts: Enabled (Click to mute)'
                      : 'Push Alerts: Muted (Click to enable)'
                    : 'Click to allow desktop notifications'
                }
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
                </svg>
              </button>
            </div>

            <div className="nav-rail-bottom">
              <div
                className="agent-profile-pill"
                title={`Active Advisor: ${agentName || 'Agent'} (Online)`}
              >
                {(agentName || 'A')[0].toUpperCase()}
                <span className="agent-online-dot"></span>
              </div>

              <button
                className="rail-logout-btn"
                onClick={handleLogout}
                title="Sign out of console"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
              </button>
            </div>
          </nav>

          {/* ── PANEL 1: CONVERSATION LIST (Column 1) ── */}
          <section className="conv-list-panel" aria-label="Conversation list">
            <div className="conv-list-header">
              <div className="conv-list-title-row">
                <span className="conv-list-title">
                  {currentTab === 'my'
                    ? 'My Inbox'
                    : currentTab === 'waiting'
                    ? 'Waiting Queue'
                    : currentTab === 'with_agent'
                    ? 'Active Chats'
                    : currentTab === 'closed'
                    ? 'History'
                    : 'All Conversations'}
                </span>
                <span className="conv-total-pill">{filteredSessions.length}</span>
              </div>

              <div className="conv-search-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8"></circle>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
                <input
                  className="conv-search-input"
                  placeholder="Search name, phone, issue..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
                {searchQuery && (
                  <button className="conv-search-clear" onClick={() => setSearchQuery('')}>
                    ×
                  </button>
                )}
              </div>

              <div className="conv-filter-tabs">
                <button
                  className={`conv-filter-tab ${currentTab === 'all' ? 'active' : ''}`}
                  onClick={() => setCurrentTab('all')}
                >
                  All
                </button>
                <button
                  className={`conv-filter-tab ${currentTab === 'waiting' ? 'active' : ''}`}
                  onClick={() => setCurrentTab('waiting')}
                >
                  Waiting
                </button>
                <button
                  className={`conv-filter-tab ${currentTab === 'with_agent' ? 'active' : ''}`}
                  onClick={() => setCurrentTab('with_agent')}
                >
                  Active
                </button>
                <button
                  className={`conv-filter-tab ${currentTab === 'closed' ? 'active' : ''}`}
                  onClick={() => setCurrentTab('closed')}
                >
                  Closed
                </button>
              </div>
            </div>

            {/* Live Queue Stat Strip */}
            <div className="queue-stats-strip">
              <div className="q-stat-card">
                <span className="q-stat-lbl">Waiting</span>
                <span className="q-stat-val waiting">{waitingCount}</span>
              </div>
              <div className="q-stat-card">
                <span className="q-stat-lbl">With Agent</span>
                <span className="q-stat-val active">{withAgentCount}</span>
              </div>
            </div>

            {/* Conversation Cards Scroll List */}
            <div className="conv-items-scroll">
              {filteredSessions.length === 0 ? (
                <div className="conv-empty-state">
                  <div className="conv-empty-icon">💬</div>
                  <div className="conv-empty-text">No conversations found</div>
                </div>
              ) : (
                filteredSessions.map(s => {
                  const isSelected = s.conversation_id === activeSessionId;
                  const initial = (s.customer?.name || '?')[0].toUpperCase();
                  const waitTimeStr = formatWaitTime(s.updated_at || s.created_at);

                  return (
                    <div
                      key={s.conversation_id}
                      className={`conv-card ${isSelected ? 'active' : ''}`}
                      onClick={() => {
                        setActiveSessionId(s.conversation_id);
                        fetchDetail(s.conversation_id);
                      }}
                    >
                      <div className="conv-card-avatar">
                        {initial}
                        {s.status === 'waiting' && <span className="conv-unread-dot" title="Waiting for advisor" />}
                      </div>

                      <div className="conv-card-content">
                        <div className="conv-card-row1">
                          <span className="conv-card-name">{s.customer?.name || 'Anonymous Customer'}</span>
                          <span className="conv-card-time">{waitTimeStr}</span>
                        </div>

                        <div className="conv-card-message">
                          {s.last_message || s.issue_type || 'AstroVed consultation request'}
                        </div>

                        <div className="conv-card-row3">
                          <span className="conv-card-topic">
                            #{s.issue_type ? s.issue_type.replace(/\s+/g, '') : 'General'}
                          </span>
                          <span className={`conv-status-pill ${s.status}`}>
                            {s.status === 'with_agent' ? 'ACTIVE' : s.status.toUpperCase()}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </section>

          {/* ── PANEL 2: MAIN CONVERSATION PANEL (Column 2) ── */}
          <main className={`conv-main-panel ${activeSessionId ? 'mobile-active' : ''}`} aria-label="Active conversation">
            {!activeSessionId || !activeDetail ? (
              <div className="conv-empty-selection">
                <div className="conv-empty-selection-icon">✦</div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
                  Select a Conversation
                </h3>
                <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 320 }}>
                  Choose a seeker from the live queue or your assigned chats to view the message history and reply.
                </p>
              </div>
            ) : (
              <>
                {/* Conversation Header */}
                <header className="conv-main-header">
                  <div className="header-left-meta">
                    <button
                      className="mobile-back-btn"
                      onClick={() => {
                        setActiveSessionId(null);
                        setActiveDetail(null);
                      }}
                      aria-label="Back to conversation list"
                      title="Back to queue"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="19" y1="12" x2="5" y2="12"></line>
                        <polyline points="12 19 5 12 12 5"></polyline>
                      </svg>
                    </button>

                    <div className="header-avatar">
                      {(activeDetail.customer?.name || '?')[0].toUpperCase()}
                    </div>

                    <div className="header-info-col">
                      <div className="header-customer-name">
                        {activeDetail.customer?.name || 'Customer'}
                        <span className={`conv-status-pill ${activeDetail.status}`}>
                          {activeDetail.status === 'with_agent' ? 'ACTIVE' : activeDetail.status.toUpperCase()}
                        </span>
                      </div>
                      <div className="header-customer-sub">
                        {activeDetail.customer?.email} {activeDetail.customer?.mobile ? `• ${activeDetail.customer.mobile}` : ''}
                      </div>
                    </div>
                  </div>

                  <div className="header-actions-group">
                    <button
                      className="action-btn-claim"
                      onClick={handleClaim}
                      disabled={
                        activeDetail.status === 'active' ||
                        activeDetail.status === 'with_agent' ||
                        activeDetail.status === 'closed' ||
                        Boolean(activeDetail.assigned_agent)
                      }
                      title={activeDetail.assigned_agent ? `Assigned to ${activeDetail.assigned_agent}` : 'Claim chat'}
                    >
                      {activeDetail.assigned_agent
                        ? activeDetail.assigned_agent === agentName
                          ? '✓ Claimed (You)'
                          : `Assigned (${activeDetail.assigned_agent})`
                        : activeDetail.status === 'closed'
                        ? 'Closed'
                        : 'Claim Chat'}
                    </button>

                    <button
                      className="action-btn-return"
                      onClick={handleReturnToBot}
                      disabled={
                        activeDetail.status === 'closed' ||
                        activeDetail.status === 'bot_active' ||
                        !activeDetail.assigned_agent
                      }
                      title="Return customer to AstroVed AI Guide and release advisor claim"
                    >
                      End &amp; Return to Bot
                    </button>

                    <button
                      className={`action-btn-details-toggle ${isRightPanelOpen ? 'active' : ''}`}
                      onClick={() => setIsRightPanelOpen(!isRightPanelOpen)}
                      title="Toggle customer details panel"
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                        <line x1="15" y1="3" x2="15" y2="21"></line>
                      </svg>
                      Details
                    </button>
                  </div>
                </header>

                {/* Message Timeline */}
                <div className="message-timeline-body" ref={chatBodyRef} onScroll={handleAgentScroll} style={{ position: 'relative' }}>
                  {isLoadingDetail && (!activeDetail.messages || activeDetail.messages.length === 0) ? (
                    <div className="system-pill-notice">Loading conversation history…</div>
                  ) : (
                    <>
                      {activeDetail.messages?.map(m => {
                        const isUser = m.sender === 'user';
                        const isAgent = m.sender === 'agent';
                        const isSystem = m.sender === 'system';
                        const timeStr = formatTimeHM(m.timestamp);

                        if (isSystem) {
                          return (
                            <div key={m.id} className="system-pill-notice">
                              {m.text}
                            </div>
                          );
                        }

                        return (
                          <div
                            key={m.id}
                            className={`chat-msg-row ${isUser ? 'user' : isAgent ? 'agent' : 'bot'}`}
                          >
                            <div className="chat-msg-bubble">
                              <MessageRenderer text={m.text} />
                            </div>
                            <div className="chat-msg-meta">
                              {!isUser && !isAgent && (
                                <span className="bot-tag-pill">AI Guide</span>
                              )}
                              {isAgent && (
                                <span style={{ fontWeight: 600 }}>{activeDetail.assigned_agent || 'Advisor'} •</span>
                              )}
                              <span>{timeStr}</span>
                            </div>
                          </div>
                        );
                      })}

                      {activeDetail.status === 'waiting' && (
                        <div className="system-pill-notice">
                          Customer waiting for advisor • Category: {activeDetail.issue_type || 'General Support'}
                        </div>
                      )}
                    </>
                  )}

                  {showAgentJump && (
                    <button
                      type="button"
                      className="jump-to-bottom-btn"
                      style={{ position: 'sticky', bottom: '16px', margin: '0 auto' }}
                      onClick={handleAgentJumpToLatest}
                      aria-label="Jump to latest messages"
                    >
                      New messages ↓
                    </button>
                  )}
                </div>

                {/* Message Composer (Docked at Bottom) */}
                <div className="conv-composer-container">
                  {/* Quick Replies Strip */}
                  <div className="composer-quick-bar">
                    <span className="composer-quick-label">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                      </svg>
                      Quick:
                    </span>
                    {QUICK_REPLIES.slice(0, 3).map((qr, idx) => (
                      <button
                        key={idx}
                        className="composer-quick-chip"
                        onClick={() => handleUseQuickReply(qr)}
                        type="button"
                      >
                        {qr.slice(0, 36)}…
                      </button>
                    ))}
                  </div>

                  {/* Input & Send Button */}
                  <div className="composer-input-row">
                    <input
                      ref={composerInputRef}
                      className="composer-input"
                      placeholder={
                        activeDetail.status === 'closed'
                          ? 'This consultation has ended — session is closed'
                          : activeDetail.status === 'bot_active' || !activeDetail.assigned_agent
                          ? 'Session handled by AstroVed AI Guide — claim chat to reply'
                          : activeDetail.status === 'waiting'
                          ? 'Customer in waiting queue — claim chat to begin replying'
                          : 'Type your message to the seeker... (Press Enter to send)'
                      }
                      value={replyInput}
                      disabled={
                        activeDetail.status === 'closed' ||
                        activeDetail.status === 'bot_active' ||
                        !activeDetail.assigned_agent
                      }
                      onChange={e => setReplyInput(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') handleSendReply();
                      }}
                    />

                    <button
                      className="composer-send-btn"
                      onClick={handleSendReply}
                      disabled={
                        activeDetail.status === 'closed' ||
                        activeDetail.status === 'bot_active' ||
                        !activeDetail.assigned_agent ||
                        !replyInput.trim()
                      }
                      aria-label="Send message"
                      title="Send message"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13"></line>
                        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                      </svg>
                    </button>
                  </div>

                  <div className="composer-hint-row">
                    <span>
                      {activeDetail.assigned_agent
                        ? `Advisor: ${activeDetail.assigned_agent}`
                        : 'Unassigned Queue'}
                    </span>
                    <span>Press Enter to send</span>
                  </div>
                </div>
              </>
            )}
          </main>

          {/* ── PANEL 3: RIGHT CUSTOMER DETAILS PANEL (Column 3) ── */}
          <aside
            className={`customer-details-panel ${isRightPanelOpen ? 'open' : ''}`}
            aria-label="Customer profile details"
          >
            <div className="details-panel-header">
              <div className="details-panel-title-row">
                <span className="details-panel-title">Customer Dossier</span>
                <button
                  className="details-close-btn"
                  onClick={() => setIsRightPanelOpen(false)}
                  title="Close details"
                >
                  ✕
                </button>
              </div>

              <div className="details-tabs-row">
                <button
                  className={`details-tab-btn ${rightPanelTab === 'user' ? 'active' : ''}`}
                  onClick={() => setRightPanelTab('user')}
                >
                  Profile
                </button>
                <button
                  className={`details-tab-btn ${rightPanelTab === 'activity' ? 'active' : ''}`}
                  onClick={() => setRightPanelTab('activity')}
                >
                  Activity
                </button>
                <button
                  className={`details-tab-btn ${rightPanelTab === 'quick' ? 'active' : ''}`}
                  onClick={() => setRightPanelTab('quick')}
                >
                  Quick Replies
                </button>
              </div>
            </div>

            <div className="details-panel-content">
              {!activeDetail ? (
                <div style={{ textAlign: 'center', padding: '40px 10px', color: 'var(--text-muted)', fontSize: 13 }}>
                  Select a conversation to see the customer profile and rating.
                </div>
              ) : rightPanelTab === 'user' ? (
                /* Profile Tab */
                <div>
                  <div className="profile-card-hero">
                    <div className="profile-avatar-large">
                      {(activeDetail.customer?.name || '?')[0].toUpperCase()}
                    </div>
                    <div className="profile-name-lg">{activeDetail.customer?.name || 'Seeker'}</div>
                    <div className="profile-email-sub">{activeDetail.customer?.email || 'No email provided'}</div>
                  </div>

                  {/* Customer Rating Section */}
                  <div className="details-section-card">
                    <div className="details-section-title">Customer Satisfaction</div>
                    {activeDetail.rating ? (
                      <div className="rating-display-box">
                        <div className="rating-stars-row">
                          {Array.from({ length: 5 }).map((_, i) => (
                            <span
                              key={i}
                              style={{ color: i < activeDetail.rating! ? 'var(--gold-600)' : 'var(--bg-muted)' }}
                            >
                              ★
                            </span>
                          ))}
                          <span className="rating-score-pill">{activeDetail.rating} / 5</span>
                        </div>
                        {activeDetail.feedback && (
                          <div className="rating-feedback-quote">
                            "{activeDetail.feedback}"
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="rating-empty-notice">
                        No customer review submitted for this session yet.
                      </div>
                    )}
                  </div>

                  {/* Metadata List */}
                  <div className="details-section-card">
                    <div className="details-section-title">Contact &amp; Session Info</div>
                    <div className="meta-kv-list">
                      <div className="meta-kv-row">
                        <span className="meta-kv-key">Phone</span>
                        <span className="meta-kv-val">
                          {activeDetail.customer?.mobile || '—'}
                          {activeDetail.customer?.mobile && (
                            <button
                              className="copy-icon-btn"
                              onClick={() => copyToClipboard(activeDetail.customer.mobile, 'Phone number')}
                              title="Copy phone"
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                              </svg>
                            </button>
                          )}
                        </span>
                      </div>

                      <div className="meta-kv-row">
                        <span className="meta-kv-key">Status</span>
                        <span className={`conv-status-pill ${activeDetail.status}`}>
                          {activeDetail.status.toUpperCase()}
                        </span>
                      </div>

                      <div className="meta-kv-row">
                        <span className="meta-kv-key">Issue Category</span>
                        <span className="meta-kv-val">{activeDetail.issue_type || 'General Astrology'}</span>
                      </div>

                      <div className="meta-kv-row">
                        <span className="meta-kv-key">Priority</span>
                        <span className="meta-kv-val" style={{ color: 'var(--text-secondary)' }}>Normal</span>
                      </div>

                      <div className="meta-kv-row">
                        <span className="meta-kv-key">Assigned Agent</span>
                        <span className="meta-kv-val">{activeDetail.assigned_agent || 'Unassigned'}</span>
                      </div>

                      <div className="meta-kv-row">
                        <span className="meta-kv-key">Session ID</span>
                        <span className="meta-kv-val code">
                          {activeDetail.conversation_id}
                          <button
                            className="copy-icon-btn"
                            onClick={() => copyToClipboard(activeDetail.conversation_id, 'Session ID')}
                            title="Copy ID"
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                          </button>
                        </span>
                      </div>

                      <div className="meta-kv-row">
                        <span className="meta-kv-key">Created</span>
                        <span className="meta-kv-val" style={{ fontSize: 11 }}>
                          {new Date(activeDetail.created_at).toLocaleString('en-GB')}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : rightPanelTab === 'activity' ? (
                /* Activity Tab */
                <div className="activity-timeline-list">
                  <div className="activity-step-item">
                    <div className="activity-step-dot"></div>
                    <div className="activity-step-title">Session Created</div>
                    <div className="activity-step-time">{new Date(activeDetail.created_at).toLocaleTimeString()}</div>
                  </div>

                  {activeDetail.is_agent_handling && (
                    <div className="activity-step-item">
                      <div className="activity-step-dot agent"></div>
                      <div className="activity-step-title">Claimed by {activeDetail.assigned_agent || 'Advisor'}</div>
                      <div className="activity-step-time">Live Support Takeover</div>
                    </div>
                  )}

                  <div className="activity-step-item">
                    <div className="activity-step-dot waiting"></div>
                    <div className="activity-step-title">{activeDetail.messages?.length || 0} Messages Recorded</div>
                    <div className="activity-step-time">Active Conversation</div>
                  </div>
                </div>
              ) : (
                /* Quick Replies Library Tab */
                <div className="qr-library-list">
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>
                    Click to insert into reply composer:
                  </div>
                  {QUICK_REPLIES.map((qr, idx) => (
                    <button
                      key={idx}
                      className="qr-card-item"
                      onClick={() => handleUseQuickReply(qr)}
                    >
                      {qr}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </aside>

          {/* ── ANALYTICS OVERLAY (Light Theme) ── */}
          {showAnalytics && (
            <div className="analytics-modal-backdrop" onClick={() => setShowAnalytics(false)}>
              <div className="analytics-modal-card" onClick={e => e.stopPropagation()}>
                <div className="analytics-header">
                  <div className="analytics-title-group">
                    <button
                      className="analytics-modal-close-btn"
                      onClick={() => setShowAnalytics(false)}
                    >
                      ← Close
                    </button>
                    <span className="analytics-title">Command Analytics</span>
                  </div>

                  <button
                    className="action-btn-return"
                    onClick={fetchAnalytics}
                    style={{ fontSize: 12, height: 32 }}
                  >
                    Refresh Data
                  </button>
                </div>

                <div className="analytics-body-scroll">
                  {/* KPI Cards */}
                  <div className="analytics-kpi-grid">
                    <div className="kpi-stat-card">
                      <span className="kpi-stat-val">
                        {analyticsData ? analyticsData.total_sessions : allSessions.length}
                      </span>
                      <span className="kpi-stat-lbl">Total Sessions</span>
                    </div>

                    <div className="kpi-stat-card">
                      <span className="kpi-stat-val" style={{ color: 'var(--status-active-dot)' }}>
                        {analyticsData ? analyticsData.resolved : allSessions.filter(s => s.status === 'closed' || s.status === 'resolved').length}
                      </span>
                      <span className="kpi-stat-lbl">Resolved</span>
                    </div>

                    <div className="kpi-stat-card">
                      <span className="kpi-stat-val" style={{ color: 'var(--gold-600)' }}>
                        {analyticsData ? analyticsData.waiting : waitingCount}
                      </span>
                      <span className="kpi-stat-lbl">Waiting Queue</span>
                    </div>

                    <div className="kpi-stat-card">
                      <span className="kpi-stat-val" style={{ color: 'var(--indigo-700)' }}>
                        {analyticsData ? analyticsData.with_agent : withAgentCount}
                      </span>
                      <span className="kpi-stat-lbl">With Advisor</span>
                    </div>
                  </div>

                  {/* Charts Grid */}
                  <div className="analytics-charts-grid">
                    <div className="chart-card">
                      <h4>Top Issue Topics</h4>
                      {analyticsData?.top_issues && analyticsData.top_issues.length > 0 ? (
                        analyticsData.top_issues.map((item, i) => (
                          <div key={i} style={{ marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                              <span>{item.name}</span>
                              <span style={{ color: 'var(--text-muted)' }}>{item.count} ({item.pct}%)</span>
                            </div>
                            <div className="issue-bar-track">
                              <div className="issue-bar-fill" style={{ width: `${item.pct}%` }}></div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
                          No consultation issues recorded yet.
                        </div>
                      )}
                    </div>

                    <div className="chart-card">
                      <h4>Queue Performance</h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-light)' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Avg Response Time</span>
                          <strong>{analyticsData?.avg_response_time_seconds ? `${analyticsData.avg_response_time_seconds}s` : 'Real-time telemetry active'}</strong>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-light)' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Bot Handling Ratio</span>
                          <strong>{analyticsData?.bot_handled ? `${analyticsData.bot_handled} sessions` : 'Active'}</strong>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
                          <span style={{ color: 'var(--text-muted)' }}>Live Queue Status</span>
                          <span style={{ color: 'var(--status-active-dot)', fontWeight: 600 }}>Optimal</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Recent Users Table */}
                  <div className="recent-users-table-card">
                    <h4>Recent Consultations</h4>
                    <table className="light-table">
                      <thead>
                        <tr>
                          <th>Customer</th>
                          <th>Email</th>
                          <th>Phone</th>
                          <th>Status</th>
                          <th>Topic</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(analyticsData?.recent_users || allSessions.slice(0, 6).map(s => ({
                          name: s.customer?.name || 'Seeker',
                          email: s.customer?.email || '—',
                          phone: s.customer?.mobile || '—',
                          status: s.status,
                          issue: s.issue_type || 'Astrology'
                        }))).map((u, idx) => (
                          <tr key={idx}>
                            <td><strong>{u.name}</strong></td>
                            <td>{u.email}</td>
                            <td>{u.phone}</td>
                            <td>
                              <span className={`conv-status-pill ${u.status.toLowerCase()}`}>
                                {u.status}
                              </span>
                            </td>
                            <td>{u.issue}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Light Toast Notification */}
      {toastMessage && (
        <div className="light-toast">
          {toastMessage}
        </div>
      )}
    </div>
  );
};
