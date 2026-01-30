import React, { useState, useEffect } from 'react';
import './MarketStatus.css';

/**
 * MarketStatus Component
 *
 * Displays the current status of the US stock market (NYSE/NASDAQ)
 * - Market Open/Closed status
 * - Countdown to next open/close
 * - Holiday detection
 * - Pre-market and After-hours indicators
 */
const MarketStatus = () => {
  const [marketStatus, setMarketStatus] = useState({
    isOpen: false,
    isPreMarket: false,
    isAfterHours: false,
    isHoliday: false,
    holidayName: null,
    nextEvent: null,
    timeUntilEvent: null,
    currentTime: null
  });

  // US Stock Market Holidays 2025
  const holidays = [
    { date: '2025-01-01', name: "New Year's Day" },
    { date: '2025-01-20', name: 'Martin Luther King Jr. Day' },
    { date: '2025-02-17', name: "Presidents' Day" },
    { date: '2025-04-18', name: 'Good Friday' },
    { date: '2025-05-26', name: 'Memorial Day' },
    { date: '2025-06-19', name: 'Juneteenth' },
    { date: '2025-07-04', name: 'Independence Day' },
    { date: '2025-09-01', name: 'Labor Day' },
    { date: '2025-11-27', name: 'Thanksgiving Day' },
    { date: '2025-12-25', name: 'Christmas Day' }
  ];

  const isHoliday = (date) => {
    const dateStr = date.toISOString().split('T')[0];
    const holiday = holidays.find(h => h.date === dateStr);
    return holiday || null;
  };

  const isWeekend = (date) => {
    const day = date.getDay();
    return day === 0 || day === 6; // Sunday or Saturday
  };

  const getNextTradingDay = (date) => {
    let nextDay = new Date(date);
    nextDay.setDate(nextDay.getDate() + 1);
    nextDay.setHours(0, 0, 0, 0);

    // Skip weekends and holidays
    while (isWeekend(nextDay) || isHoliday(nextDay)) {
      nextDay.setDate(nextDay.getDate() + 1);
    }

    return nextDay;
  };

  const calculateMarketStatus = () => {
    // Get current time in ET (US/Eastern)
    const now = new Date();
    const etTime = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));

    const hours = etTime.getHours();
    const minutes = etTime.getMinutes();
    const currentMinutes = hours * 60 + minutes;

    // Market hours (ET)
    const preMarketStart = 4 * 60;      // 4:00 AM
    const marketOpen = 9 * 60 + 30;     // 9:30 AM
    const marketClose = 16 * 60;        // 4:00 PM
    const afterHoursEnd = 20 * 60;      // 8:00 PM

    // Check if today is a holiday
    const holiday = isHoliday(etTime);
    const weekend = isWeekend(etTime);

    let status = {
      isOpen: false,
      isPreMarket: false,
      isAfterHours: false,
      isHoliday: holiday !== null,
      holidayName: holiday ? holiday.name : null,
      currentTime: etTime.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/New_York',
        timeZoneName: 'short'
      })
    };

    if (holiday || weekend) {
      // Market closed for holiday or weekend
      const nextTrading = getNextTradingDay(etTime);
      nextTrading.setHours(9, 30, 0, 0);

      status.nextEvent = 'Market Opens';
      status.timeUntilEvent = nextTrading - etTime;
    } else {
      // Regular trading day
      if (currentMinutes >= marketOpen && currentMinutes < marketClose) {
        // Market is OPEN
        status.isOpen = true;
        status.nextEvent = 'Market Closes';

        const closeTime = new Date(etTime);
        closeTime.setHours(16, 0, 0, 0);
        status.timeUntilEvent = closeTime - etTime;

      } else if (currentMinutes >= preMarketStart && currentMinutes < marketOpen) {
        // Pre-market hours
        status.isPreMarket = true;
        status.nextEvent = 'Market Opens';

        const openTime = new Date(etTime);
        openTime.setHours(9, 30, 0, 0);
        status.timeUntilEvent = openTime - etTime;

      } else if (currentMinutes >= marketClose && currentMinutes < afterHoursEnd) {
        // After-hours trading
        status.isAfterHours = true;
        status.nextEvent = 'After-Hours Ends';

        const afterHoursEndTime = new Date(etTime);
        afterHoursEndTime.setHours(20, 0, 0, 0);
        status.timeUntilEvent = afterHoursEndTime - etTime;

      } else {
        // Market closed (before pre-market or after after-hours)
        status.nextEvent = 'Pre-Market Opens';

        let nextOpen = new Date(etTime);
        if (currentMinutes >= afterHoursEnd) {
          // After 8 PM, next open is tomorrow
          nextOpen.setDate(nextOpen.getDate() + 1);
        }
        nextOpen.setHours(4, 0, 0, 0);

        // Skip to next trading day if weekend
        if (isWeekend(nextOpen)) {
          nextOpen = getNextTradingDay(nextOpen);
          nextOpen.setHours(4, 0, 0, 0);
        }

        status.timeUntilEvent = nextOpen - etTime;
      }
    }

    setMarketStatus(status);
  };

  useEffect(() => {
    // Calculate immediately
    calculateMarketStatus();

    // Update every second
    const interval = setInterval(calculateMarketStatus, 1000);

    return () => clearInterval(interval);
  }, []);

  const formatTimeRemaining = (ms) => {
    if (!ms || ms < 0) return '0h 0m';

    const totalSeconds = Math.floor(ms / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 24) {
      const days = Math.floor(hours / 24);
      const remainingHours = hours % 24;
      return `${days}d ${remainingHours}h`;
    }

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }

    return `${minutes}m ${seconds}s`;
  };

  const getStatusBadge = () => {
    if (marketStatus.isHoliday) {
      return {
        text: `🎉 HOLIDAY - ${marketStatus.holidayName}`,
        className: 'holiday',
        icon: '🎉'
      };
    }

    if (marketStatus.isOpen) {
      return {
        text: '🟢 MARKET OPEN',
        className: 'open',
        icon: '🟢'
      };
    }

    if (marketStatus.isPreMarket) {
      return {
        text: '🟡 PRE-MARKET',
        className: 'pre-market',
        icon: '🟡'
      };
    }

    if (marketStatus.isAfterHours) {
      return {
        text: '🟠 AFTER-HOURS',
        className: 'after-hours',
        icon: '🟠'
      };
    }

    return {
      text: '🔴 MARKET CLOSED',
      className: 'closed',
      icon: '🔴'
    };
  };

  const badge = getStatusBadge();

  return (
    <div className={`market-status ${badge.className}`}>
      <div className="status-badge">
        <span className="status-icon">{badge.icon}</span>
        <span className="status-text">{badge.text}</span>
      </div>

      {marketStatus.nextEvent && (
        <div className="next-event">
          <span className="event-label">{marketStatus.nextEvent} in:</span>
          <span className="event-countdown">{formatTimeRemaining(marketStatus.timeUntilEvent)}</span>
        </div>
      )}

      <div className="current-time">
        <span className="time-label">ET:</span>
        <span className="time-value">{marketStatus.currentTime}</span>
      </div>
    </div>
  );
};

export default MarketStatus;
