import React, { useState } from 'react';
import { CustomerLead } from '../types';
import { ArrowRight, Compass } from 'lucide-react';

interface WelcomeFormProps {
  onSubmit: (lead: CustomerLead & { initial_query?: string }) => void;
  isLoading: boolean;
}

export const WelcomeForm: React.FC<WelcomeFormProps> = ({ onSubmit, isLoading }) => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [topic, setTopic] = useState('Career & Professional Growth');
  const [initialQuery, setInitialQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !mobile.trim()) return;

    onSubmit({
      name: name.trim(),
      email: email.trim(),
      mobile: mobile.trim(),
      topic_of_interest: topic,
      initial_query: initialQuery.trim() || undefined,
    });
  };

  return (
    <div className="lead-card-wrapper">
      <div className="lead-card-header">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '0.8rem' }}>
          <div className="brand-logo-badge">
            <Compass size={24} color="#0d0f1c" />
          </div>
        </div>
        <h2>AstroVed AI Guide</h2>
        <p>
          Connect with timeless Vedic wisdom. Enter your details to begin your personalized astrological consultation.
        </p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="name-input">Full Name *</label>
          <input
            id="name-input"
            className="form-input"
            type="text"
            placeholder="e.g. Rahul Sharma"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="email-input">Email Address *</label>
          <input
            id="email-input"
            className="form-input"
            type="email"
            placeholder="e.g. rahul.sharma@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="mobile-input">Mobile Number *</label>
          <input
            id="mobile-input"
            className="form-input"
            type="tel"
            placeholder="e.g. +91 98765 43210"
            value={mobile}
            onChange={(e) => setMobile(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="topic-select">Primary Area of Life</label>
          <select
            id="topic-select"
            className="form-select"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          >
            <option value="Career & Professional Growth">Career & Professional Growth (10th House)</option>
            <option value="Relationships & Marriage Compatibility">Relationships & Marriage (7th House)</option>
            <option value="Wealth, Finance & Prosperity">Wealth & Finance (2nd & 11th House)</option>
            <option value="Health, Vitality & Well-being">Health & Vitality (1st House & Sun)</option>
            <option value="Planetary Transits & Sade Sati">Planetary Transits & Sade Sati</option>
            <option value="General Vedic Astrology & Remedies">General Vedic Astrology & Remedies</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="query-input">Your Question or Focus (Optional)</label>
          <textarea
            id="query-input"
            className="form-textarea"
            rows={2}
            placeholder="e.g. What remedies strengthen my Saturn during this dasha?"
            value={initialQuery}
            onChange={(e) => setInitialQuery(e.target.value)}
          />
        </div>

        <button
          type="submit"
          className="submit-btn"
          disabled={isLoading || !name.trim() || !email.trim() || !mobile.trim()}
        >
          {isLoading ? (
            'Preparing Astrological Session...'
          ) : (
            <>
              <span>Begin Vedic Consultation</span>
              <ArrowRight size={18} />
            </>
          )}
        </button>
      </form>
    </div>
  );
};
