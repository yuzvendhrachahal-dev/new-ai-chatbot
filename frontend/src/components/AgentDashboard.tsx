import React, { useState, useEffect, useRef } from 'react';
import { ConversationSummary, ConversationDetail, AnalyticsData } from '../types';
import { chatApi } from '../api';
import { ASTROVED_LOGO } from '../assets/logo';
import '../styles/agent-dashboard.css';

interface AgentDashboardProps {
  onSwitchToCustomer?: () => void;
}

type TabType = 'all' | 'waiting' | 'with_agent' | 'closed';
type RightPanelTab = 'user' | 'activity' | 'quick';

const QUICK_REPLIES = [
  "Thank you for reaching out! How can I assist you today?",
  "I'm checking your account details now, please hold on.",
  "Your request has been noted. Our team will follow up shortly.",
  "Could you please provide your registered email address?",
  "I understand your concern. Let me escalate this for you.",
  "Is there anything else I can help you with today?",
  "Your issue has been resolved. Have a wonderful day! ✨"
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
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [replyInput, setReplyInput] = useState('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);

  const chatBodyRef = useRef<HTMLDivElement | null>(null);

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

  const handleTogglePushNotifications = async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      showToast('Push notifications not supported in this browser.');
      return;
    }

    if (Notification.permission === 'granted') {
      const next = !pushEnabled;
      setPushEnabled(next);
      localStorage.setItem('av_push_enabled', String(next));
      showToast(next ? '🔔 Push notifications enabled!' : '🔕 Push notifications muted.');
    } else if (Notification.permission === 'denied') {
      showToast('Notifications are blocked by browser. Please enable in site settings.');
    } else {
      try {
        const permission = await Notification.requestPermission();
        setNotificationPermission(permission);
        if (permission === 'granted') {
          setPushEnabled(true);
          localStorage.setItem('av_push_enabled', 'true');
          showToast('🔔 Push notifications allowed successfully!');
          try {
            new Notification('AstroVed CRM Support', {
              body: 'Desktop notifications are active. You will be alerted of incoming seeker chats.',
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

  const showToast = (msg: string, duration = 3000) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), duration);
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
          } catch {
            // notification failed
          }
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
    } catch {
      // silent
    }
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

  // Scroll messages to bottom on detail update
  useEffect(() => {
    if (chatBodyRef.current) {
      chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
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

        // Ask for browser notification permission natively
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
      // Optimistically disable Claim Chat immediately
      setActiveDetail(prev => prev ? {
        ...prev,
        status: 'active',
        assigned_agent: agentName,
        is_agent_handling: true
      } : prev);

      await chatApi.claimChat(activeSessionId, agentName, agentToken);
      showToast('Chat claimed successfully! 🤝');
      await fetchDetail(activeSessionId);
      await fetchSessions();
    } catch (err: any) {
      showToast(err.message || 'Could not claim chat (already claimed or unavailable)');
      // Refresh immediately on conflict (HTTP 409)
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
      showToast('Returned session to AI guide. Assignment cleared.');
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
  };

  // Filtered session list
  const filteredSessions = allSessions.filter(s => {
    if (currentTab === 'waiting' && s.status !== 'waiting') return false;
    if (currentTab === 'with_agent' && s.status !== 'with_agent' && s.status !== 'active') return false;
    if (currentTab === 'closed' && s.status !== 'closed' && s.status !== 'resolved') return false;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = (s.customer?.name || '').toLowerCase().includes(q);
      const matchEmail = (s.customer?.email || '').toLowerCase().includes(q);
      const matchPhone = (s.customer?.mobile || '').toLowerCase().includes(q);
      const matchId = (s.conversation_id || '').toLowerCase().includes(q);
      return matchName || matchEmail || matchPhone || matchId;
    }
    return true;
  });

  const waitingCount = allSessions.filter(s => s.status === 'waiting').length;
  const withAgentCount = allSessions.filter(
    s => (s.status === 'with_agent' || s.status === 'active') && s.is_agent_handling
  ).length;

  const formatCardDateTime = (isoString?: string): string => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      const datePart = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
      const timePart = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
      return `${datePart} • ${timePart}`;
    } catch {
      return '';
    }
  };

  return (
    <div style={{ position: 'relative', width: '100%', minHeight: '100vh', background: 'var(--bg)' }}>
      {/* Aurora Ambient Glow */}
      <div className="aurora">
        <div className="ab"></div>
        <div className="ab"></div>
        <div className="ab"></div>
        <div className="ab"></div>
      </div>
      <div className="grd"></div>

      {/* ── 1. LOGIN SCREEN ── */}
      {!isLoggedIn ? (
        <div id="ls" style={{ display: 'flex' }}>
          <div className="lcard">
            <div className="lorb">
              <img id="login-logo" src={ASTROVED_LOGO} alt="AstroVed" />
            </div>
            <div className="ltitle">AstroVed</div>
            <div className="lsub">CRM SUPPORT CONSOLE</div>

            <form onSubmit={handleLogin}>
              <div className="lg">
                <label htmlFor="lu">Username</label>
                <input
                  id="lu"
                  type="text"
                  placeholder="agent1"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  autoComplete="username"
                  required
                />
              </div>

              <div className="lg">
                <label htmlFor="lp">Password</label>
                <div className="pass-wrap">
                  <input
                    id="lp"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    autoComplete="current-password"
                    required
                  />
                  <button
                    type="button"
                    className="toggle-pass-btn"
                    id="togglePassBtn"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label="Toggle password visibility"
                    title="Toggle password visibility"
                  >
                    {!showPassword ? (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                      </svg>
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                        <line x1="1" y1="1" x2="23" y2="23"></line>
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <button className="lbtn" type="submit">
                Enter Console ✦
              </button>
            </form>

            <div className="lerr" id="le" style={{ display: loginError ? 'block' : 'none' }}>
              {loginError || 'Invalid credentials — please try again'}
            </div>
          </div>
        </div>
      ) : (
        /* ── 2. APP CONSOLE ── */
        <div id="app" className="on" style={{ display: 'flex' }}>
          {/* Top Navigation */}
          <nav id="nav">
            <img className="nlogo" id="nav-logo" src={ASTROVED_LOGO} alt="AstroVed" />
            <div className="nbrand">
              AstroVed <em>Support Console</em>
            </div>
            <div className="nsep"></div>

            {/* Push Notifications Allow/Block Button */}
            <button
              className={`nbtn notif-btn ${
                notificationPermission === 'granted' && pushEnabled
                  ? 'active'
                  : notificationPermission === 'denied'
                  ? 'blocked'
                  : 'prompt'
              }`}
              onClick={handleTogglePushNotifications}
              title={
                notificationPermission === 'granted'
                  ? pushEnabled
                    ? 'Push Notifications: Active (Click to mute)'
                    : 'Push Notifications: Muted (Click to enable)'
                  : notificationPermission === 'denied'
                  ? 'Push Notifications: Blocked in browser settings'
                  : 'Click to allow desktop notifications'
              }
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z"/>
              </svg>
              {notificationPermission === 'granted' && pushEnabled
                ? 'Push: Active'
                : notificationPermission === 'granted' && !pushEnabled
                ? 'Push: Muted'
                : notificationPermission === 'denied'
                ? 'Push: Blocked'
                : 'Allow Push'}
            </button>

            <div className="npill" id="npill">
              Support Agent 1
            </div>

            <button
              className="nbtn ana"
              id="anabtn"
              onClick={() => {
                setShowAnalytics(!showAnalytics);
                if (!showAnalytics) fetchAnalytics();
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <path d="M3 13h2v7H3v-7zm4-6h2v13H7V7zm4 3h2v10h-2V10zm4-7h2v17h-2V3zm4 4h2v13h-2V7z" />
              </svg>
              Analytics
            </button>

            <button className="nbtn lo" onClick={handleLogout}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5-5-5zm-5 12H5V5h7V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7v-2z" />
              </svg>
              Log out
            </button>
          </nav>

          <div id="body" className={activeSessionId ? 'chat-active' : ''}>
            {/* ── SIDEBAR: LIVE QUEUE ── */}
            <div id="sb">
              <div className="sb-top">
                <div className="sb-head">
                  <h3>⚡ LIVE QUEUE</h3>
                  <span className="qbadge" id="qbadge">
                    {waitingCount + withAgentCount}
                  </span>
                </div>

                <div className="sb-search">
                  <svg viewBox="0 0 24 24">
                    <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
                  </svg>
                  <input
                    id="srch"
                    placeholder="Search users…"
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                </div>

                <div className="sb-tabs">
                  <button
                    className={`sb-tab ${currentTab === 'all' ? 'on' : ''}`}
                    onClick={() => setCurrentTab('all')}
                  >
                    All
                  </button>
                  <button
                    className={`sb-tab ${currentTab === 'waiting' ? 'on' : ''}`}
                    onClick={() => setCurrentTab('waiting')}
                  >
                    Waiting
                  </button>
                  <button
                    className={`sb-tab ${currentTab === 'with_agent' ? 'on' : ''}`}
                    onClick={() => setCurrentTab('with_agent')}
                  >
                    Active
                  </button>
                  <button
                    className={`sb-tab ${currentTab === 'closed' ? 'on' : ''}`}
                    onClick={() => setCurrentTab('closed')}
                  >
                    History
                  </button>
                </div>
              </div>

              <div className="sb-stats">
                <div className="ss-card">
                  <div className="ss-val" id="ss-w" style={{ color: 'var(--waiting)' }}>
                    {waitingCount}
                  </div>
                  <div className="ss-lbl">Waiting</div>
                </div>
                <div className="ss-card">
                  <div className="ss-val" id="ss-a" style={{ color: 'var(--active)' }}>
                    {withAgentCount}
                  </div>
                  <div className="ss-lbl">With Agent</div>
                </div>
              </div>

              {/* Sessions List */}
              <div id="sl">
                {filteredSessions.length === 0 ? (
                  <div className="sb-empty">
                    <div>⚡</div>
                    <p>No active chats</p>
                  </div>
                ) : (
                  filteredSessions.map(s => {
                    const isSelected = s.conversation_id === activeSessionId;
                    const initial = (s.customer?.name || '?')[0].toUpperCase();
                    const statusClass =
                      s.status === 'waiting'
                        ? 'waiting'
                        : s.status === 'with_agent' || s.status === 'active'
                        ? 'with_agent'
                        : 'closed';

                    return (
                      <div
                        key={s.conversation_id}
                        className={`sc ${isSelected ? 'on' : ''}`}
                        onClick={() => {
                          setActiveSessionId(s.conversation_id);
                          fetchDetail(s.conversation_id);
                        }}
                      >
                        <div className="sc-av">{initial}</div>
                        <div className="sc-body">
                          <div className="sc-r1">
                            <div className="sc-name">{s.customer?.name || 'Anonymous User'}</div>
                            <span className={`sc-badge ${statusClass}`}>
                              {s.status === 'with_agent' ? 'ACTIVE' : s.status.toUpperCase()}
                            </span>
                          </div>
                          <div className="sc-sub">
                            {s.customer?.email || 'user@example.com'} • {formatCardDateTime(s.updated_at)}
                          </div>
                          <div className="sc-issue">
                            Issue: {s.issue_type ? s.issue_type.charAt(0).toUpperCase() + s.issue_type.slice(1) : 'General'}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* ── CHAT PANEL ── */}
            <div id="cp">
              {!activeSessionId || !activeDetail ? (
                <div id="cp-empty" className="cp-empty" style={{ display: 'flex', flex: 1 }}>
                  <div className="icon">✦</div>
                  <p>Select a conversation from the queue</p>
                </div>
              ) : (
                <div id="cp-chat" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, height: '100%', maxHeight: '100%', overflow: 'hidden' }}>
                  {/* Chat Panel Header */}
                  <div id="ch">
                    <button
                      className="hbtn back-btn"
                      onClick={() => {
                        setActiveSessionId(null);
                        setActiveDetail(null);
                      }}
                      aria-label="Back to session list"
                      title="Back"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
                      </svg>
                    </button>

                    <div className="ch-av" id="ch-av">
                      {(activeDetail.customer?.name || '?')[0].toUpperCase()}
                    </div>

                    <div className="ch-info">
                      <h3 id="ch-name">{activeDetail.customer?.name || 'Customer'}</h3>
                      <p id="ch-sub">
                        {activeDetail.customer?.email || ''} {activeDetail.customer?.mobile ? `• ${activeDetail.customer.mobile}` : ''}
                      </p>
                      <div className="ch-tags" id="ch-tags">
                        <span className={`tag status-${activeDetail.status}`}>
                          {activeDetail.status === 'with_agent' ? 'active' : activeDetail.status.toLowerCase()}
                        </span>
                        <span className="tag">
                          {activeDetail.issue_type || 'support_request'}
                        </span>
                      </div>
                    </div>

                    <div className="ch-actions">
                      <button
                        className="hbtn claim"
                        onClick={handleClaim}
                        disabled={
                          activeDetail.status === 'active' ||
                          activeDetail.status === 'with_agent' ||
                          activeDetail.status === 'closed' ||
                          Boolean(activeDetail.assigned_agent)
                        }
                      >
                        {activeDetail.assigned_agent
                          ? activeDetail.assigned_agent === agentName
                            ? 'Claimed (You)'
                            : `Assigned (${activeDetail.assigned_agent})`
                          : activeDetail.status === 'closed'
                          ? 'Closed'
                          : 'Claim Chat'}
                      </button>
                      <button
                        className="hbtn return"
                        onClick={handleReturnToBot}
                        disabled={
                          activeDetail.status === 'closed' ||
                          activeDetail.status === 'bot_active' ||
                          !activeDetail.assigned_agent
                        }
                        title="End live advisor consultation and return customer to AstroVed AI Guide"
                      >
                        End &amp; Return to Bot
                      </button>
                    </div>
                  </div>

                  {/* Messages History Body (WhatsApp Style) */}
                  <div id="cb" ref={chatBodyRef}>
                    {isLoadingDetail && (!activeDetail.messages || activeDetail.messages.length === 0) ? (
                      <div className="ld">
                        <div className="sp"></div>Loading messages…
                      </div>
                    ) : (
                      <>
                        {activeDetail.messages?.map(m => {
                          const isUser = m.sender === 'user';
                          const isAgent = m.sender === 'agent';
                          const isSystem = m.sender === 'system';
                          const timeStr = formatCardDateTime(m.timestamp);

                          if (isSystem) {
                            return (
                              <div key={m.id} className="msg system">
                                {m.text}
                              </div>
                            );
                          }

                          return (
                            <div
                              key={m.id}
                              className={`msg ${isUser ? 'user' : isAgent ? 'agent' : 'bot'}`}
                            >
                              <div className="msg-bubble">
                                <div className="msg-text">{m.text}</div>
                                <div className="msg-time">{timeStr}</div>
                              </div>
                            </div>
                          );
                        })}

                        {activeDetail.status === 'waiting' && (
                          <div className="msg system">
                            Handoff requested: {activeDetail.issue_type || 'support_request'} (priority: normal)
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {/* Reply Input Bar */}
                  <div id="rb">
                    <input
                      id="ri"
                      placeholder={
                        activeDetail.status === 'closed'
                          ? 'Session closed — new messages cannot be sent'
                          : activeDetail.status === 'bot_active' || !activeDetail.assigned_agent
                          ? 'Session returned to AI Guide — claim chat to reply'
                          : activeDetail.status === 'waiting'
                          ? 'Claim chat to begin replying...'
                          : 'Type your reply...'
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
                      id="rs"
                      onClick={handleSendReply}
                      aria-label="Send reply"
                      disabled={
                        activeDetail.status === 'closed' ||
                        activeDetail.status === 'bot_active' ||
                        !activeDetail.assigned_agent ||
                        !replyInput.trim()
                      }
                    >
                      <svg viewBox="0 0 24 24">
                        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                      </svg>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* ── RIGHT PANEL ── */}
            <div id="rp">
              <div className="rp-tabs">
                <button
                  className={`rp-tab ${rightPanelTab === 'user' ? 'on' : ''}`}
                  onClick={() => setRightPanelTab('user')}
                >
                  User
                </button>
                <button
                  className={`rp-tab ${rightPanelTab === 'activity' ? 'on' : ''}`}
                  onClick={() => setRightPanelTab('activity')}
                >
                  Activity
                </button>
                <button
                  className={`rp-tab ${rightPanelTab === 'quick' ? 'on' : ''}`}
                  onClick={() => setRightPanelTab('quick')}
                >
                  Quick
                </button>
              </div>

              {/* User Tab */}
              <div className="rp-body" id="rp-user" style={{ display: rightPanelTab === 'user' ? 'block' : 'none' }}>
                {!activeDetail ? (
                  <div className="ucard">
                    <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--muted)', fontSize: 12 }}>
                      <div style={{ fontSize: 34, opacity: 0.14, color: 'var(--purple)', marginBottom: 10 }}>◈</div>
                      Select a chat to see user details
                    </div>
                  </div>
                ) : (
                  <div className="ucard">
                    <div className="user-hero">
                      <div className="user-av-large">{(activeDetail.customer?.name || '?')[0].toUpperCase()}</div>
                      <h4>{activeDetail.customer?.name || 'Seeker'}</h4>
                      <p>{activeDetail.customer?.email || 'No email provided'}</p>
                    </div>

                    <div className="user-details-list">
                      <div className="ud-row">
                        <span className="ud-label">PHONE</span>
                        <span className="ud-val">{activeDetail.customer?.mobile || '—'}</span>
                      </div>
                      <div className="ud-row">
                        <span className="ud-label">STATUS</span>
                        <span className={`ud-val status-${activeDetail.status}`}>
                          {activeDetail.status === 'with_agent' ? 'ACTIVE' : activeDetail.status.toUpperCase()}
                        </span>
                      </div>
                      <div className="ud-row">
                        <span className="ud-label">ISSUE TYPE</span>
                        <span className="ud-val">{activeDetail.issue_type || 'support_request'}</span>
                      </div>
                      <div className="ud-row">
                        <span className="ud-label">PRIORITY</span>
                        <span className="ud-val">normal</span>
                      </div>
                      <div className="ud-row">
                        <span className="ud-label">ASSIGNED AGENT</span>
                        <span className="ud-val">{activeDetail.assigned_agent || 'Unassigned'}</span>
                      </div>
                      <div className="ud-row">
                        <span className="ud-label">SESSION ID</span>
                        <span className="ud-val code">{activeDetail.conversation_id}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Activity Tab */}
              <div className="rp-body" id="rp-activity" style={{ display: rightPanelTab === 'activity' ? 'block' : 'none' }}>
                {!activeDetail ? (
                  <div className="a-empty">Select a chat to see activity</div>
                ) : (
                  <div className="activity-timeline">
                    <div className="act-item">
                      <div className="act-dot"></div>
                      <div className="act-content">
                        <div className="act-title">Session Created</div>
                        <div className="act-time">
                          {new Date(activeDetail.created_at).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                    {activeDetail.is_agent_handling && (
                      <div className="act-item">
                        <div className="act-dot agent"></div>
                        <div className="act-content">
                          <div className="act-title">Claimed by {activeDetail.assigned_agent || 'Advisor'}</div>
                          <div className="act-time">Live Support Mode</div>
                        </div>
                      </div>
                    )}
                    <div className="act-item">
                      <div className="act-dot message"></div>
                      <div className="act-content">
                        <div className="act-title">{activeDetail.messages?.length || 0} Total Messages Exchanged</div>
                        <div className="act-time">Active Conversation</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Quick Replies Tab */}
              <div className="rp-body" id="rp-quick" style={{ display: rightPanelTab === 'quick' ? 'block' : 'none' }}>
                <div className="qr-section">
                  <div className="qr-label">Quick Replies</div>
                  <div className="qr-chips">
                    {QUICK_REPLIES.map((qr, idx) => (
                      <button
                        key={idx}
                        className="qr-chip"
                        onClick={() => handleUseQuickReply(qr)}
                      >
                        {qr}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* ── ANALYTICS OVERLAY ── */}
            <div id="ap" style={{ display: showAnalytics ? 'flex' : 'none' }}>
              <div className="aw">
                <div className="ana-hdr">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <button
                      className="hbtn back-btn"
                      onClick={() => setShowAnalytics(false)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: 6,
                        background: 'rgba(255,255,255,0.05)',
                        border: '1px solid var(--border)',
                        color: 'var(--text)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        cursor: 'pointer'
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
                      </svg>
                      Back
                    </button>
                    <div>
                      <div className="at">✦ Command Analytics</div>
                      <div className="at-sub" id="ats">
                        Live stream data from AstroVed support engine
                      </div>
                    </div>
                  </div>

                  <div className="hdr-actions">
                    <div className="live-pill">
                      <div className="ldot"></div>LIVE
                    </div>
                    <button className="icon-btn" onClick={fetchAnalytics}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
                      </svg>
                      Refresh
                    </button>
                  </div>
                </div>

                {/* KPI Cards */}
                <div className="sg">
                  <div className="scard c1">
                    <div className="cb"></div>
                    <div className="shimmer"></div>
                    <div className="ico">💬</div>
                    <div className="sv" id="st">
                      {analyticsData ? analyticsData.total_sessions : allSessions.length}
                    </div>
                    <div className="sl2">Total Sessions</div>
                  </div>
                  <div className="scard c2">
                    <div className="cb"></div>
                    <div className="shimmer"></div>
                    <div className="ico">✅</div>
                    <div className="sv" id="sc2">
                      {analyticsData ? analyticsData.resolved : allSessions.filter(s => s.status === 'closed' || s.status === 'resolved').length}
                    </div>
                    <div className="sl2">Resolved</div>
                  </div>
                  <div className="scard c3">
                    <div className="cb"></div>
                    <div className="shimmer"></div>
                    <div className="ico">⏳</div>
                    <div className="sv" id="sw">
                      {analyticsData ? analyticsData.waiting : waitingCount}
                    </div>
                    <div className="sl2">Waiting</div>
                  </div>
                  <div className="scard c4">
                    <div className="cb"></div>
                    <div className="shimmer"></div>
                    <div className="ico">🤝</div>
                    <div className="sv" id="sa">
                      {analyticsData ? analyticsData.with_agent : withAgentCount}
                    </div>
                    <div className="sl2">With Agent</div>
                  </div>
                </div>

                {/* Charts */}
                <div className="cg">
                  <div className="cc">
                    <h4>Top Issue Types</h4>
                    <div id="ibars">
                      {analyticsData?.top_issues && analyticsData.top_issues.length > 0 ? (
                        analyticsData.top_issues.map((item, i) => (
                          <div key={i} className="issue-bar-row" style={{ marginBottom: 12 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                              <span>{item.name}</span>
                              <span style={{ color: 'var(--muted)' }}>{item.count} ({item.pct}%)</span>
                            </div>
                            <div style={{ height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 3, overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${item.pct}%`, background: 'var(--purple)', borderRadius: 3 }}></div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div style={{ color: 'var(--muted)', fontSize: 12, padding: '16px 0', textAlign: 'center' }}>
                          No consultation issue topics recorded yet.
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="cc">
                    <h4>Status Mix</h4>
                    <div className="dw">
                      <svg className="ds" viewBox="0 0 42 42" id="donut">
                        <circle cx="21" cy="21" r="15.9" fill="transparent" stroke="rgba(0,245,255,.05)" strokeWidth="6" />
                        <circle
                          cx="21"
                          cy="21"
                          r="15.9"
                          fill="transparent"
                          stroke="#22C55E"
                          strokeWidth="6"
                          strokeDasharray="40 60"
                          strokeDashoffset="25"
                        />
                        <circle
                          cx="21"
                          cy="21"
                          r="15.9"
                          fill="transparent"
                          stroke="#F2B84B"
                          strokeWidth="6"
                          strokeDasharray="30 70"
                          strokeDashoffset="85"
                        />
                        <circle
                          cx="21"
                          cy="21"
                          r="15.9"
                          fill="transparent"
                          stroke="#34D399"
                          strokeWidth="6"
                          strokeDasharray="30 70"
                          strokeDashoffset="55"
                        />
                      </svg>
                      <div className="dl" id="dleg">
                        {analyticsData?.status_mix ? (
                          analyticsData.status_mix.map((item, idx) => (
                            <div key={idx} className="leg-item">
                              <span className="dot" style={{ background: item.color }}></span>
                              {item.status} ({item.count})
                            </div>
                          ))
                        ) : (
                          <>
                            <div className="leg-item"><span className="dot" style={{ background: '#F2B84B' }}></span>Waiting ({waitingCount})</div>
                            <div className="leg-item"><span className="dot" style={{ background: '#22C55E' }}></span>With Agent ({withAgentCount})</div>
                            <div className="leg-item"><span className="dot" style={{ background: '#34D399' }}></span>Resolved</div>
                          </>
                        )}
                      </div>
                    </div>
                    {analyticsData?.avg_response_time_seconds !== undefined && (
                      <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 14, textAlign: 'center' }}>
                        Avg Advisor Response Time: <strong style={{ color: 'var(--text)' }}>{analyticsData.avg_response_time_seconds > 0 ? `${analyticsData.avg_response_time_seconds}s` : 'Real-time telemetry active'}</strong>
                      </div>
                    )}
                  </div>
                </div>

                {/* Recent Users Table */}
                <div className="utc">
                  <h4>Recent Users</h4>
                  <div className="tbl-w">
                    <table>
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Email</th>
                          <th>Phone</th>
                          <th>Status</th>
                          <th>Issue</th>
                          <th>Date</th>
                        </tr>
                      </thead>
                      <tbody id="utb">
                        {(analyticsData?.recent_users || allSessions.slice(0, 8).map(s => ({
                          name: s.customer?.name || 'Seeker',
                          email: s.customer?.email || '—',
                          phone: s.customer?.mobile || '—',
                          status: s.status,
                          issue: s.issue_type || 'Astrology',
                          date: new Date(s.created_at).toLocaleDateString()
                        }))).map((u, idx) => (
                          <tr key={idx}>
                            <td><strong>{u.name}</strong></td>
                            <td>{u.email}</td>
                            <td>{u.phone}</td>
                            <td>
                              <span className={`sc-badge ${u.status.toLowerCase()}`}>
                                {u.status}
                              </span>
                            </td>
                            <td>{u.issue}</td>
                            <td>{u.date}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div id="toast" className="on">
          {toastMessage}
        </div>
      )}
    </div>
  );
};
