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
      {currentView === 'customer' ? (
        <CustomerChatbot onSwitchToAgent={() => switchView('agent')} />
      ) : (
        <AgentDashboard onSwitchToCustomer={() => switchView('customer')} />
      )}
    </div>
  );
};

export default App;
