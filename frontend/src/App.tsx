import React, { useState, useEffect } from 'react';
import { CustomerChatbot } from './components/CustomerChatbot';
import { AgentDashboard } from './components/AgentDashboard';

export const App: React.FC = () => {
  const getInitialView = (): 'customer' | 'agent' => {
    const path = window.location.pathname.toLowerCase();
    if (path.includes('/agent')) {
      return 'agent';
    }
    return 'customer';
  };

  const [currentView, setCurrentView] = useState<'customer' | 'agent'>(getInitialView);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentView(getInitialView());
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const switchView = (view: 'customer' | 'agent') => {
    setCurrentView(view);
    const newPath = view === 'agent' ? '/agent/dashboard' : '/app';
    window.history.pushState({}, '', newPath);
  };

  return (
    <div className="astroved-root-app">
      {/* Discreet floating mode switcher for testing/evaluating both screens */}
      <div className="view-mode-floating-bar">
        <button
          className={`mode-btn ${currentView === 'customer' ? 'active' : ''}`}
          onClick={() => switchView('customer')}
          title="Customer Chatbot View (/app)"
        >
          <span>Chatbot (/app)</span>
        </button>
        <button
          className={`mode-btn ${currentView === 'agent' ? 'active' : ''}`}
          onClick={() => switchView('agent')}
          title="Agent Console View (/agent/dashboard)"
        >
          <span>Agent Console (/agent)</span>
        </button>
      </div>

      {currentView === 'customer' ? (
        <CustomerChatbot onSwitchToAgent={() => switchView('agent')} />
      ) : (
        <AgentDashboard onSwitchToCustomer={() => switchView('customer')} />
      )}
    </div>
  );
};

export default App;
