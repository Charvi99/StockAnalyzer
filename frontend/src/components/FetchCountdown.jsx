import React, { useState, useEffect } from 'react';
import './FetchCountdown.css';

/**
 * FetchCountdown Component
 *
 * Displays a countdown timer showing when the next data fetch will occur.
 * Updates every second and shows time remaining in HH:MM:SS format.
 *
 * @param {Date|string} nextFetchAt - The timestamp when next fetch is scheduled
 * @param {Date|string} lastFetchAt - The timestamp of the last fetch (optional)
 * @param {boolean} compact - Whether to show compact view (default: false)
 */
const FetchCountdown = ({ nextFetchAt, lastFetchAt, compact = false }) => {
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [isOverdue, setIsOverdue] = useState(false);

  useEffect(() => {
    if (!nextFetchAt) {
      setTimeRemaining(null);
      return;
    }

    // Calculate time remaining
    const calculateTimeRemaining = () => {
      const now = new Date();
      const targetTime = new Date(nextFetchAt);
      const diff = targetTime - now;

      if (diff <= 0) {
        setIsOverdue(true);
        setTimeRemaining({ hours: 0, minutes: 0, seconds: 0 });
        return;
      }

      setIsOverdue(false);
      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      setTimeRemaining({ hours, minutes, seconds });
    };

    // Calculate immediately
    calculateTimeRemaining();

    // Update every second
    const interval = setInterval(calculateTimeRemaining, 1000);

    return () => clearInterval(interval);
  }, [nextFetchAt]);

  // If no next fetch time, don't render
  if (!nextFetchAt || timeRemaining === null) {
    return null;
  }

  const formatTime = (value) => String(value).padStart(2, '0');

  // Format last fetch time
  const formatLastFetch = () => {
    if (!lastFetchAt) return 'Never';

    const lastFetch = new Date(lastFetchAt);
    const now = new Date();
    const diffMs = now - lastFetch;
    const diffMins = Math.floor(diffMs / (1000 * 60));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  if (compact) {
    // Compact view for StockCard top-right corner
    return (
      <div className={`fetch-countdown-compact ${isOverdue ? 'overdue' : ''}`}>
        <div className="countdown-icon">⏱️</div>
        <div className="countdown-time">
          {isOverdue ? (
            <span className="overdue-text">Fetching...</span>
          ) : (
            <span>
              {formatTime(timeRemaining.hours)}:{formatTime(timeRemaining.minutes)}:{formatTime(timeRemaining.seconds)}
            </span>
          )}
        </div>
      </div>
    );
  }

  // Full view for detail pages
  return (
    <div className={`fetch-countdown ${isOverdue ? 'overdue' : ''}`}>
      <div className="countdown-header">
        <span className="countdown-label">Next Update</span>
        {lastFetchAt && (
          <span className="last-fetch-label">Last: {formatLastFetch()}</span>
        )}
      </div>
      <div className="countdown-timer">
        {isOverdue ? (
          <div className="countdown-overdue">
            <span className="overdue-icon">🔄</span>
            <span className="overdue-text">Update in progress...</span>
          </div>
        ) : (
          <div className="countdown-display">
            <div className="countdown-segment">
              <span className="countdown-value">{formatTime(timeRemaining.hours)}</span>
              <span className="countdown-unit">hours</span>
            </div>
            <div className="countdown-separator">:</div>
            <div className="countdown-segment">
              <span className="countdown-value">{formatTime(timeRemaining.minutes)}</span>
              <span className="countdown-unit">mins</span>
            </div>
            <div className="countdown-separator">:</div>
            <div className="countdown-segment">
              <span className="countdown-value">{formatTime(timeRemaining.seconds)}</span>
              <span className="countdown-unit">secs</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FetchCountdown;
