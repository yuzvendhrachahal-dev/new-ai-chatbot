import React, { useState, useEffect, useRef } from 'react';
import { CustomerLead, MessageItem } from '../types';
import { chatApi } from '../api';
import { ASTROVED_LOGO } from '../assets/logo';
import { MessageRenderer } from './MessageRenderer';
import '../styles/customer-chatbot.css';

interface CustomerChatbotProps {
  onSwitchToAgent?: () => void;
}

type ChatScreenState = 'registration' | 'chat' | 'crm' | 'ended';

const COUNTRY_CODES = [
  { code: '+91', label: '🇮🇳 +91' },
  { code: '+1', label: '🇺🇸 +1' },
  { code: '+44', label: '🇬🇧 +44' },
  { code: '+61', label: '🇦🇺 +61' },
  { code: '+971', label: '🇦🇪 +971' },
  { code: '+65', label: '🇸🇬 +65' },
  { code: '+60', label: '🇲🇾 +60' },
  { code: '+94', label: '🇱🇰 +94' },
  { code: '+880', label: '🇧🇩 +880' },
  { code: '+92', label: '🇵🇰 +92' },
  { code: '+66', label: '🇹🇭 +66' },
  { code: '+81', label: '🇯🇵 +81' },
  { code: '+82', label: '🇰🇷 +82' },
  { code: '+86', label: '🇨🇳 +86' },
  { code: '+33', label: '🇫🇷 +33' },
  { code: '+49', label: '🇩🇪 +49' },
  { code: '+55', label: '🇧🇷 +55' },
  { code: '+27', label: '🇿🇦 +27' },
  { code: '+90', label: '🇹🇷 +90' },
  { code: '+966', label: '🇸🇦 +966' }
];

const getStoredSessionId = (): string | null => {
  try {
    if (typeof window === 'undefined') return null;
    return sessionStorage.getItem('astroved_session_id') || localStorage.getItem('astroved_session_id');
  } catch {
    return null;
  }
};

const saveSessionId = (id: string) => {
  try {
    sessionStorage.setItem('astroved_session_id', id);
    localStorage.setItem('astroved_session_id', id);
  } catch {}
};

const clearStoredSession = () => {
  try {
    sessionStorage.removeItem('astroved_session_id');
    localStorage.removeItem('astroved_session_id');
  } catch {}
};

const isIgnoredSystemMessage = (m: MessageItem) => {
  if (!m || !m.text) return false;
  if (m.sender === 'system') return true;
  if (m.text.includes('Message delivered to your assigned AstroVed Advisor')) return true;
  return false;
};

const mergeMessageList = (prev: MessageItem[], incoming: MessageItem[]): MessageItem[] => {
  if (!incoming || incoming.length === 0) return prev;

  // Filter out any system delivery notifications
  const sanitizedIncoming = incoming.filter(m => !isIgnoredSystemMessage(m));
  if (sanitizedIncoming.length === 0) return prev;

  const result = [...(prev || []).filter(m => !isIgnoredSystemMessage(m))];

  for (const inc of sanitizedIncoming) {
    if (!inc || !inc.id) continue;

    // 1. Direct match by canonical server ID
    const exactIndex = result.findIndex(m => m.id === inc.id);
    if (exactIndex !== -1) {
      result[exactIndex] = { ...result[exactIndex], ...inc };
      continue;
    }

    // 2. Incoming message is from user: match and replace the most recent in-flight optimistic message
    if (inc.sender === 'user') {
      let optUserIndex = -1;
      for (let i = result.length - 1; i >= 0; i--) {
        const m = result[i];
        if (m.sender === 'user' && (m.id.startsWith('user-') || m.id.startsWith('temp-')) && m.text.trim() === inc.text.trim()) {
          optUserIndex = i;
          break;
        }
      }
      if (optUserIndex !== -1) {
        result[optUserIndex] = inc;
        continue;
      }
    }

    // 3. Initial welcome message reconciliation:
    // Only reconcile if result[0] is an in-flight client welcome placeholder (e.g. id 'msg-welcome')
    // and incoming is the canonical server welcome message for the session.
    // Never mutate, replace, or overwrite the initial welcome when answering greetings like 'hi'.
    if (
      inc.sender === 'assistant' &&
      result.length > 0 &&
      (result[0].id === 'msg-welcome' || result[0].id.startsWith('msg-welcome')) &&
      (result[0].text.trim() === inc.text.trim() || inc.text.includes('Vedic AI Astrology guide'))
    ) {
      result[0] = inc;
      continue;
    }

    // 4. Fallback deduplication: same sender, same text, and timestamps within 3 seconds
    // Only applies if matching against an in-flight optimistic client message (user-* or temp-*)
    const incTime = new Date(inc.timestamp || 0).getTime();
    const dupIndex = result.findIndex(
      m => m.sender === inc.sender &&
           m.text.trim() === inc.text.trim() &&
           (m.id.startsWith('user-') || m.id.startsWith('temp-')) &&
           Math.abs(new Date(m.timestamp || 0).getTime() - incTime) < 3000
    );
    if (dupIndex !== -1) {
      result[dupIndex] = inc;
      continue;
    }

    // 5. Append new distinct message
    result.push(inc);
  }

  // Preserve stable chronological order by timestamp
  result.sort((a, b) => {
    const tA = new Date(a.timestamp || 0).getTime();
    const tB = new Date(b.timestamp || 0).getTime();
    if (!isNaN(tA) && !isNaN(tB) && tA !== tB && tA > 0 && tB > 0) {
      return tA - tB;
    }
    return 0;
  });

  return result;
};

export const CustomerChatbot: React.FC<CustomerChatbotProps> = () => {
  const initialSavedId = getStoredSessionId();
  const [screen, setScreen] = useState<ChatScreenState>(initialSavedId ? 'chat' : 'registration');
  const [isWindowOpen, setIsWindowOpen] = useState(true);
  const [isLauncherMenuOpen, setIsLauncherMenuOpen] = useState(false);
  const [showEndDialog, setShowEndDialog] = useState(false);

  // Form inputs
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [countryCode, setCountryCode] = useState('+91');
  const [phone, setPhone] = useState('');
  const [formError, setFormError] = useState('');
  const [shakingField, setShakingField] = useState<'name' | 'email' | 'phone' | null>(null);

  // Chat session data
  const [conversationId, setConversationId] = useState<string | null>(initialSavedId);
  const [customer, setCustomer] = useState<CustomerLead | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string>('bot_active');
  const [assignedAgent, setAssignedAgent] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isListening, setIsListening] = useState(false);

  // Rating state
  const [selectedRating, setSelectedRating] = useState<number>(5);
  const [hoverRating, setHoverRating] = useState<number | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const [isRatingSubmitted, setIsRatingSubmitted] = useState(false);
  const [isSubmittingRating, setIsSubmittingRating] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const isAtBottomRef = useRef<boolean>(true);
  const [showJumpToBottom, setShowJumpToBottom] = useState<boolean>(false);
  const prevMessagesCountRef = useRef<number>(0);

  const handleScroll = () => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const threshold = 70; // px threshold from bottom
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const isBottom = distanceFromBottom <= threshold;
    isAtBottomRef.current = isBottom;
    if (isBottom) {
      setShowJumpToBottom(false);
    }
  };

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
    setShowJumpToBottom(false);
    isAtBottomRef.current = true;
  };

  // Starfield animation
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let stars: Array<{ x: number; y: number; r: number; a: number; da: number }> = [];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      stars = [];
      for (let i = 0; i < 140; i++) {
        stars.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          r: Math.random() * 1.3 + 0.2,
          a: Math.random(),
          da: (Math.random() * 0.003 + 0.001) * (Math.random() < 0.5 ? 1 : -1)
        });
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      stars.forEach(p => {
        p.a += p.da;
        if (p.a > 1 || p.a < 0.1) p.da *= -1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(210,200,170,${p.a})`;
        ctx.fill();
      });
      animId = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener('resize', resize);
    draw();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animId);
    };
  }, []);

  // Smart scroll preservation: Auto-scroll only when user is near bottom; preserve position if reading history
  useEffect(() => {
    if (screen !== 'chat') return;

    const prevCount = prevMessagesCountRef.current;
    const currentCount = messages.length;
    const hasNewMessages = currentCount > prevCount;
    prevMessagesCountRef.current = currentCount;

    if (prevCount === 0 || isAtBottomRef.current) {
      scrollToBottom('smooth');
    } else if (hasNewMessages) {
      setShowJumpToBottom(true);
    }
  }, [messages, screen]);

  // Check and restore saved session from storage
  useEffect(() => {
    const savedId = getStoredSessionId();
    if (!savedId) {
      setScreen('registration');
      return;
    }

    setConversationId(savedId);

    let isMounted = true;
    chatApi.getMessages(savedId)
      .then(data => {
        if (!isMounted) return;
        setCustomer({
          name: data.customer_name || 'Seeker',
          email: '',
          mobile: ''
        });
        if (data.status) setSessionStatus(data.status);
        if (data.assigned_agent !== undefined) setAssignedAgent(data.assigned_agent);
        if (data.rating) {
          setSelectedRating(data.rating);
          setIsRatingSubmitted(true);
        }
        if (data.feedback) {
          setFeedbackText(data.feedback);
        }

        if (data.messages && data.messages.length > 0) {
          setMessages(prev => mergeMessageList(prev, data.messages));
        }

        // Restore correct screen based on session lifecycle
        if (data.status === 'closed') {
          setScreen('ended');
        } else {
          setScreen('chat');
        }
      })
      .catch((err: any) => {
        if (!isMounted) return;
        // Only clear if the backend explicitly returned 404 (session truly does not exist)
        if (err?.status === 404) {
          clearStoredSession();
          setConversationId(null);
          setScreen('registration');
        } else {
          // Network interruption: preserve session and stay on current screen
          console.warn('Network issue restoring session, keeping session state active:', err);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Real-time SSE stream for customer conversation updates & replies with reconnect
  useEffect(() => {
    if (!conversationId || screen === 'registration') return;

    let es: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let retryDelay = 1000;
    let isDisposed = false;

    const connectSSE = () => {
      if (isDisposed) return;
      if (es) es.close();

      es = new EventSource(`/api/chat/${conversationId}/events`);

      es.onopen = () => {
        retryDelay = 1000;
      };

      es.addEventListener('message', (e: MessageEvent) => {
        try {
          const payload = JSON.parse(e.data);
          const newMsg = payload?.message;
          if (newMsg && newMsg.id) {
            setMessages(prev => mergeMessageList(prev, [newMsg]));
          }
        } catch {}
      });

      es.addEventListener('status_change', (e: MessageEvent) => {
        try {
          const payload = JSON.parse(e.data);
          if (payload.status) {
            setSessionStatus(payload.status);
            if (payload.assigned_agent !== undefined) {
              setAssignedAgent(payload.assigned_agent);
            }
            if (payload.status === 'closed') {
              setScreen('ended');
            }
            // Refresh messages and status on status change
            chatApi.getMessages(conversationId).then(data => {
              if (data?.messages) setMessages(prev => mergeMessageList(prev, data.messages));
              if (data?.status) {
                setSessionStatus(data.status);
                if (data.status === 'closed') setScreen('ended');
              }
              if (data?.assigned_agent !== undefined) setAssignedAgent(data.assigned_agent);
            }).catch(() => {});
          }
        } catch {}
      });

      es.onerror = () => {
        if (es) es.close();
        if (!isDisposed && !reconnectTimer) {
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            retryDelay = Math.min(retryDelay * 1.5, 10000);
            connectSSE();
          }, retryDelay);
        }
      };
    };

    connectSSE();

    const handleOnline = () => {
      retryDelay = 1000;
      connectSSE();
      chatApi.getMessages(conversationId).then(data => {
        if (data?.messages) setMessages(prev => mergeMessageList(prev, data.messages));
        if (data?.status) {
          setSessionStatus(data.status);
          if (data.status === 'closed') setScreen('ended');
        }
      }).catch(() => {});
    };

    window.addEventListener('online', handleOnline);

    return () => {
      isDisposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      window.removeEventListener('online', handleOnline);
      if (es) es.close();
    };
  }, [conversationId, screen]);

  // Polling fallback for live agent responses & message synchronization
  useEffect(() => {
    if (!conversationId || screen === 'registration') return;
    const interval = setInterval(async () => {
      try {
        const data = await chatApi.getMessages(conversationId);
        if (data && data.messages) {
          if (data.status) {
            setSessionStatus(data.status);
            if (data.status === 'closed' && screen !== 'ended') {
              setScreen('ended');
            }
          }
          if (data.assigned_agent !== undefined) setAssignedAgent(data.assigned_agent);
          setMessages(prev => mergeMessageList(prev, data.messages));
        }
      } catch {
        // silent catch during polling
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [conversationId, screen]);

  const handleStartConsulting = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    const trimmedName = name.trim();
    const trimmedEmail = email.trim();
    const trimmedPhone = phone.trim();

    if (!trimmedName || !trimmedEmail || !trimmedPhone) {
      let msg = 'Please complete all required fields to continue.';
      if (!trimmedPhone && trimmedName && trimmedEmail) {
        msg = 'Please enter your phone number.';
        setShakingField('phone');
      } else if (!trimmedEmail) {
        setShakingField('email');
      } else if (!trimmedName) {
        setShakingField('name');
      }
      setFormError(msg);
      setTimeout(() => setShakingField(null), 800);
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setFormError('Please enter a valid email address.');
      setShakingField('email');
      setTimeout(() => setShakingField(null), 800);
      return;
    }

    if (trimmedPhone.length < 7) {
      setFormError('Please enter a valid phone number.');
      setShakingField('phone');
      setTimeout(() => setShakingField(null), 800);
      return;
    }

    const lead: CustomerLead = {
      name: trimmedName,
      email: trimmedEmail,
      mobile: `${countryCode} ${trimmedPhone}`,
      topic_of_interest: 'General Vedic Astrology'
    };

    try {
      setIsTyping(true);
      const res = await chatApi.startChat(lead);
      setConversationId(res.conversation_id);
      setCustomer(res.customer);
      saveSessionId(res.conversation_id);

      // Single initial greeting using the backend-generated text and canonical ID
      const welcomeText = res.welcome_message || `Namaste ${trimmedName}! Welcome to AstroVed. I am your Vedic AI Astrology guide. How may I assist your life path, birth chart queries, or remedies today?`;
      const welcomeId = res.welcome_message_id || `msg-welcome`;
      const initialMsgs: MessageItem[] = [
        {
          id: welcomeId,
          sender: 'assistant',
          text: welcomeText,
          timestamp: new Date().toISOString()
        }
      ];

      setMessages(initialMsgs);
      setScreen('chat');

      // Sync canonical server message
      chatApi.getMessages(res.conversation_id).then(data => {
        if (data?.messages && data.messages.length > 0) {
          setMessages(prev => mergeMessageList(prev, data.messages));
        }
      }).catch(() => {});
    } catch (err: any) {
      setFormError(err.message || 'Could not connect. Please try again.');
    } finally {
      setIsTyping(false);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || !conversationId) return;

    setInputText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    const tempMsg: MessageItem = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => mergeMessageList(prev, [tempMsg]));
    setIsTyping(true);

    try {
      const res = await chatApi.sendMessage(conversationId, text);
      const incoming: MessageItem[] = [];
      if (res?.user_message) incoming.push(res.user_message);
      if (res?.reply && !isIgnoredSystemMessage(res.reply)) {
        incoming.push(res.reply);
      }
      setMessages(prev => mergeMessageList(prev, incoming));
    } catch (err: any) {
      const errMsg = String(err?.message || '');
      const textToDisplay = errMsg.toLowerCase().includes('closed')
        ? 'This consultation session has been closed. Please refresh or start a new chat to consult again.'
        : 'I apologize, but I had trouble reaching the astrological chart server. Please try asking again.';
      setMessages(prev => mergeMessageList(prev, [
        {
          id: `err-${Date.now()}`,
          sender: 'assistant',
          text: textToDisplay,
          timestamp: new Date().toISOString()
        }
      ]));
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  const handleRequestHumanSupport = async (issueType?: string) => {
    if (!conversationId) {
      setScreen('crm');
      return;
    }
    try {
      setSessionStatus('waiting');
      const res = await chatApi.handoff(conversationId, issueType || 'Live Advisor Request');
      if (res?.message) {
        setMessages(prev => mergeMessageList(prev, [res.message]));
      }
    } catch {
      // silent handoff record
    }
  };

  const handleConfirmEnd = async () => {
    setShowEndDialog(false);
    if (conversationId) {
      try {
        await chatApi.endChat(conversationId);
      } catch {
        // end call
      }
    }
    setSessionStatus('closed');
    // Note: session is kept in storage so refresh preserves the ended/rating screen
    setScreen('ended');
  };

  const handleSubmitRating = async () => {
    if (!conversationId) return;
    setIsSubmittingRating(true);
    try {
      await chatApi.submitRating(conversationId, selectedRating, feedbackText.trim() || undefined);
      setIsRatingSubmitted(true);
    } catch (err) {
      console.error('Failed to submit rating:', err);
      // Still show recorded confirmation so user is not stuck
      setIsRatingSubmitted(true);
    } finally {
      setIsSubmittingRating(false);
    }
  };

  const handleRestart = () => {
    clearStoredSession();
    setConversationId(null);
    setCustomer(null);
    setSessionStatus('bot_active');
    setAssignedAgent(null);
    setMessages([]);
    setName('');
    setEmail('');
    setPhone('');
    setFormError('');
    setShowEndDialog(false);
    setSelectedRating(5);
    setHoverRating(null);
    setFeedbackText('');
    setIsRatingSubmitted(false);
    setIsSubmittingRating(false);
    setScreen('registration');
  };

  const toggleVoice = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Voice recognition is not supported in this browser. Please type your message.');
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = false;

      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => setIsListening(false);

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          setInputText(transcript);
          handleSendMessage(transcript);
        }
      };

      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  const renderCleanText = (txt: string) => {
    // Simple parser for bold **text** and newlines
    const formatted = txt
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br/>');
    return <span dangerouslySetInnerHTML={{ __html: formatted }} />;
  };

  return (
    <div style={{ position: 'relative', minHeight: '100vh', width: '100%', overflowX: 'hidden' }}>
      {/* Background Starfield Canvas */}
      <canvas id="cv" ref={canvasRef} />

      {/* Floating Launcher (Bottom Right) */}
      <div id="launcher">
        <div id="launcher-menu" className={isLauncherMenuOpen ? 'show' : ''}>
          <div
            className="launch-opt lo-wa"
            onClick={() => {
              window.open(
                'https://api.whatsapp.com/send?phone=919677391109&text=' +
                  encodeURIComponent('Hello, I visited AstroVed and need help.'),
                '_blank'
              );
              setIsLauncherMenuOpen(false);
            }}
          >
            <div className="lo-icon">
              <svg viewBox="0 0 24 24">
                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
              </svg>
            </div>
            <div className="lo-text">WhatsApp</div>
          </div>
          <div
            className="launch-opt lo-support"
            onClick={() => {
              setIsLauncherMenuOpen(false);
              setIsWindowOpen(true);
            }}
          >
            <div className="lo-icon">
              <svg viewBox="0 0 24 24">
                <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" />
              </svg>
            </div>
            <div className="lo-text">Support Chat</div>
          </div>
        </div>

        <button
          id="launcher-fab"
          className={isLauncherMenuOpen ? 'open' : ''}
          onClick={() => {
            if (isWindowOpen) {
              setIsWindowOpen(false);
            } else {
              setIsLauncherMenuOpen(!isLauncherMenuOpen);
            }
          }}
          aria-label="Open chat"
        >
          <div id="launcher-badge" style={{ display: isWindowOpen ? 'none' : 'flex' }}>1</div>
          <svg id="fab-icon-msg" viewBox="0 0 24 24" style={{ display: isLauncherMenuOpen ? 'none' : 'block' }}>
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" />
          </svg>
          <svg id="fab-icon-close" viewBox="0 0 24 24" style={{ display: isLauncherMenuOpen ? 'block' : 'none' }}>
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
          </svg>
        </button>
      </div>

      {/* Main Chat Window */}
      <div id="win" className={isWindowOpen ? 'open' : ''} role="dialog" aria-label="AstroVed.AI Chat">
        {/* Header */}
        <div className="hdr">
          <img className="logo-img" id="hdr-logo" src={ASTROVED_LOGO} alt="AstroVed" />
          <div className="hinfo">
            <div className="hname">AstroVed.AI</div>
            <div className="hsub">
              <span className={`odot ${sessionStatus === 'active' ? 'active' : sessionStatus === 'waiting' ? 'waiting' : ''}`}></span>
              {sessionStatus === 'waiting'
                ? 'Connecting to Support Team…'
                : sessionStatus === 'active'
                ? `Advisor Connected (${assignedAgent || 'Live Advisor'})`
                : customer
                ? `Online • Welcome, ${customer.name.split(' ')[0]}`
                : 'Online — Ask me anything'}
            </div>
          </div>

          <div className="hbtns">
            {(screen === 'chat' || screen === 'crm') && (
              <>
                <button
                  className="ch-hbtn crm-btn"
                  onClick={() => handleRequestHumanSupport('Live Advisor Request')}
                  aria-label="Talk to team"
                  title="Talk to Human Advisor"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M9 11H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2zm2-7h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11z" />
                  </svg>
                  <span className="tip">Talk to Team</span>
                </button>

                <button
                  className="ch-hbtn end-btn"
                  onClick={() => setShowEndDialog(true)}
                  aria-label="End chat"
                  title="End Chat"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                  </svg>
                  <span className="tip">End Chat</span>
                </button>
              </>
            )}

            <button
              className="ch-hbtn min-btn"
              onClick={() => setIsWindowOpen(false)}
              aria-label="Minimize"
              title="Minimize"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 13H5v-2h14v2z" />
              </svg>
              <span className="tip">Minimize</span>
            </button>
          </div>
        </div>

        {/* End Conversation Confirmation Dialog Overlay */}
        <div id="eo" className={showEndDialog ? 'show' : ''} style={{ display: showEndDialog ? 'flex' : 'none' }}>
          <div className="eo-ring">
            <div className="eo-icon">✦</div>
          </div>
          <div className="eo-divider"></div>
          <div className="eo-title">End Conversation?</div>
          <div className="eo-sub">
            Your cosmic session will close. The stars will always guide you back.
          </div>
          <div className="eo-btns">
            <button className="eo-btn cancel" onClick={() => setShowEndDialog(false)}>
              ← Stay
            </button>
            <button className="eo-btn confirm" onClick={handleConfirmEnd}>
              End Chat
            </button>
          </div>
        </div>

        {/* 1. Welcome / Pre-chat Registration Form Screen */}
        <div
          className="scr"
          id="fs"
          style={{ display: screen === 'registration' ? 'flex' : 'none' }}
        >
          <div className="form-body">
            <div className="fhero">
              <img className="fhero-logo" id="form-logo" src={ASTROVED_LOGO} alt="AstroVed" />
              <h2>Begin Your Journey</h2>
              <p>Share a little about yourself to get started.</p>
            </div>

            {formError && (
              <div id="form-error-msg" className="form-error-msg" role="alert" style={{ display: 'block' }}>
                {formError}
              </div>
            )}

            <form onSubmit={handleStartConsulting}>
              <div className="fg">
                <label htmlFor="fn">Your Name</label>
                <input
                  type="text"
                  id="fn"
                  className={shakingField === 'name' ? 'err' : ''}
                  placeholder="e.g. Arjun Sharma"
                  value={name}
                  onChange={e => {
                    setName(e.target.value);
                    if (formError) setFormError('');
                  }}
                  autoComplete="name"
                />
              </div>

              <div className="fg">
                <label htmlFor="fe">Email Address</label>
                <input
                  type="email"
                  id="fe"
                  className={shakingField === 'email' ? 'err' : ''}
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => {
                    setEmail(e.target.value);
                    if (formError) setFormError('');
                  }}
                  autoComplete="email"
                />
              </div>

              <div className="fg">
                <label htmlFor="fp">Phone Number</label>
                <div className="phone-row">
                  <select
                    id="fcc"
                    className="cc"
                    value={countryCode}
                    onChange={e => setCountryCode(e.target.value)}
                    aria-label="Country code"
                  >
                    {COUNTRY_CODES.map(c => (
                      <option key={c.code} value={c.code}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="tel"
                    id="fp"
                    className={shakingField === 'phone' ? 'err' : ''}
                    placeholder="98765 43210"
                    value={phone}
                    onChange={e => {
                      setPhone(e.target.value);
                      if (formError) setFormError('');
                    }}
                    autoComplete="tel"
                  />
                </div>
              </div>

              <button className="sbtn" id="start-btn" type="submit" disabled={isTyping}>
                {isTyping ? '✦ Connecting…' : '✦  Start Consulting'}
              </button>
              <p className="prv" id="prv-msg">
                🔒 Your information is private &amp; secure
              </p>
            </form>
          </div>
        </div>

        {/* 2. Chat Conversation Screen */}
        <div
          className="scr"
          id="cs"
          style={{ display: screen === 'chat' ? 'flex' : 'none' }}
        >
          {/* Active Status Banner: Only shown when waiting for advisor, active with advisor, or closed */}
          {(sessionStatus === 'waiting' || sessionStatus === 'active' || sessionStatus === 'closed') && (
            <div className={`active-handoff-bar ${sessionStatus}`}>
              {sessionStatus === 'waiting' ? (
                <div className="handoff-status-text">
                  <span className="live-dot" style={{ background: '#f59e0b', boxShadow: '0 0 6px #f59e0b' }}></span>
                  <strong>Connecting to an AstroVed Advisor…</strong> Your request is in queue.
                </div>
              ) : sessionStatus === 'active' ? (
                <div className="handoff-status-text">
                  <span className="live-dot"></span>
                  <strong>Connected with Live Advisor:</strong> {assignedAgent || 'AstroVed Live Advisor'}
                </div>
              ) : (
                <>
                  <div className="handoff-status-text">
                    <span>🔒</span>
                    This consultation is closed.
                  </div>
                  <button className="restart-mini-btn" onClick={handleRestart}>
                    ✦ Start New Consultation
                  </button>
                </>
              )}
            </div>
          )}

          <div id="msgs" ref={messagesContainerRef} onScroll={handleScroll}>
            {/* Welcome Hero Banner */}
            <div className="wcard welcome-hero">
              <img src={ASTROVED_LOGO} className="hero-logo" alt="AstroVed" />
              <h2>✨ Welcome to AstroVed.AI</h2>
              <p className="hero-sub">Your Personal Vedic Astrology Assistant</p>
              <div className="hero-topics">
                <p>Ask anything about:</p>
                <ul>
                  <li>• Horoscope</li>
                  <li>• Compatibility</li>
                  <li>• Pujas</li>
                  <li>• Numerology</li>
                  <li>• Birth Chart</li>
                  <li>• Gemstones</li>
                </ul>
              </div>
            </div>

            {/* Messages Stream */}
            {messages.filter(m => !isIgnoredSystemMessage(m)).map(m => {
              if (m.sender === 'user') {
                return (
                  <div key={m.id} className="mrow user">
                    <div className="bbl user">{renderCleanText(m.text)}</div>
                  </div>
                );
              } else {
                return (
                  <div key={m.id} className="mrow bot">
                    <div className="av bot">
                      <img src={ASTROVED_LOGO} alt="bot" />
                    </div>
                    <div className="bbl bot">
                      {m.sender === 'agent' && (
                        <div style={{ fontSize: '11px', color: 'var(--gold)', fontWeight: 600, marginBottom: 4 }}>
                          ✦ AstroVed Live Advisor
                        </div>
                      )}
                      <MessageRenderer text={m.text} />
                    </div>
                  </div>
                );
              }
            })}

            {/* Typing Indicator */}
            {isTyping && (
              <div className="mrow bot">
                <div className="av bot">
                  <img src={ASTROVED_LOGO} alt="bot" />
                </div>
                <div className="bbl bot typing">
                  <div className="typing-dots">
                    <span className="dot"></span>
                    <span className="dot"></span>
                    <span className="dot"></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Jump to Latest Messages Button */}
          {showJumpToBottom && (
            <button
              type="button"
              className="jump-to-bottom-btn"
              onClick={() => scrollToBottom('smooth')}
              aria-label="Jump to latest messages"
            >
              New messages ↓
            </button>
          )}

          {/* Input Bar */}
          <div className="ibar">
            <button
              id="vbtn"
              className={isListening ? 'listening' : ''}
              onClick={toggleVoice}
              aria-label="Voice input"
              title={isListening ? 'Listening...' : 'Voice Search'}
            >
              <svg viewBox="0 0 24 24">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
              </svg>
            </button>

            <textarea
              ref={textareaRef}
              id="inp"
              placeholder="Ask about your Questions Here"
              rows={1}
              value={inputText}
              onChange={handleTextareaInput}
              onKeyDown={handleKeyDown}
            />

            <button
              id="send-btn"
              onClick={() => handleSendMessage()}
              aria-label="Send"
              disabled={!inputText.trim()}
            >
              <svg viewBox="0 0 24 24">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </div>
        </div>

        {/* 3. CRM / Support Contact Panel Screen */}
        <div
          className="scr"
          id="crm-panel"
          style={{ display: screen === 'crm' ? 'flex' : 'none' }}
        >
          <div className="crm-hdr">
            <h3>🎧 Connect with Our Team</h3>
            <p>Choose how you'd like to reach us</p>
          </div>

          <div className="crm-contacts">
            <a
              className="crm-contact-btn crm-wa"
              href="https://api.whatsapp.com/send?phone=919677391109&text=Hello%2C%20I%20need%20assistance."
              target="_blank"
              rel="noopener noreferrer"
            >
              <div className="crm-icon">
                <svg viewBox="0 0 24 24">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                </svg>
              </div>
              <div className="crm-text">
                <div className="ct">WhatsApp Us</div>
                <div className="cn">+91 96773 91109</div>
              </div>
            </a>

            <a className="crm-contact-btn crm-mail" href="mailto:support@astroved.com">
              <div className="crm-icon">
                <svg viewBox="0 0 24 24">
                  <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
                </svg>
              </div>
              <div className="crm-text">
                <div className="ct">Email Support</div>
                <div className="cn">support@astroved.com</div>
              </div>
            </a>

            <a className="crm-contact-btn crm-phone" href="tel:+919677391108">
              <div className="crm-icon">
                <svg viewBox="0 0 24 24">
                  <path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z" />
                </svg>
              </div>
              <div className="crm-text">
                <div className="ct">Call Us</div>
                <div className="cn">+91 96773 91108</div>
              </div>
            </a>
          </div>

          <button className="crm-back" onClick={() => setScreen('chat')}>
            ← Back to Chat
          </button>
        </div>

        {/* 4. Ended / Thank You Screen */}
        <div
          className="scr"
          id="ended"
          style={{ display: screen === 'ended' ? 'flex' : 'none' }}
        >
          <div className="ended-logo-wrap">
            <img className="ended-logo" id="ended-logo" src={ASTROVED_LOGO} alt="AstroVed" />
          </div>
          <div className="ended-title">Thank You! 🙏</div>
          <div className="ended-sub">
            Your cosmic consultation has concluded.
            <br />
            May the wisdom of the stars illuminate your path always.
          </div>

          {/* Rating Section */}
          <div className="rating-card">
            <div className="rating-question">How would you rate your experience?</div>
            <div className="rating-stars" role="radiogroup" aria-label="Rating">
              {[1, 2, 3, 4, 5].map(star => {
                const isActive = (hoverRating !== null ? hoverRating : selectedRating) >= star;
                return (
                  <button
                    key={star}
                    type="button"
                    className={`star-btn ${isActive ? 'on' : ''}`}
                    onClick={() => !isRatingSubmitted && setSelectedRating(star)}
                    onMouseEnter={() => !isRatingSubmitted && setHoverRating(star)}
                    onMouseLeave={() => !isRatingSubmitted && setHoverRating(null)}
                    disabled={isRatingSubmitted || isSubmittingRating}
                    aria-label={`${star} star${star > 1 ? 's' : ''}`}
                  >
                    ★
                  </button>
                );
              })}
            </div>

            {isRatingSubmitted ? (
              <div className="rate-thanks">
                ✓ Thank you! Your rating and feedback have been recorded.
              </div>
            ) : (
              <div className="rating-form">
                <textarea
                  className="rating-feedback-input"
                  rows={2}
                  placeholder="Optional: Tell us what you liked or how we can improve..."
                  value={feedbackText}
                  onChange={e => setFeedbackText(e.target.value)}
                  disabled={isSubmittingRating}
                  maxLength={500}
                />
                <button
                  type="button"
                  className="rating-submit-btn"
                  onClick={handleSubmitRating}
                  disabled={isSubmittingRating}
                >
                  {isSubmittingRating ? 'Saving...' : 'Submit Rating ✦'}
                </button>
              </div>
            )}
          </div>

          <div style={{ margin: '8px 0', fontSize: '12px', color: 'var(--gold)', fontWeight: 600, letterSpacing: '0.03em' }}>
            ✦ AstroVed — Vedic Wisdom, Modern Guidance ✦
          </div>

          <button className="restart-btn" onClick={handleRestart}>
            ✦ Start New Consultation
          </button>
        </div>

        {/* Window Footer */}
        <div className="ft">Powered by AstroVed.AI ✦</div>
      </div>
    </div>
  );
};
