import React, { useEffect, useRef, useState, memo } from 'react';
import { createChart } from 'lightweight-charts';

const StockChart = memo(({ prices, symbol, stockId, indicatorParams, patterns = [], chartPatterns = [], highlightedPattern = null }) => {
  const chartContainerRef = useRef();
  const chartRef = useRef(null);
  const seriesRefs = useRef({});
  const trendlineRefs = useRef([]); // Track chart pattern trendline series

  const [selectedIndicators, setSelectedIndicators] = useState({
    ma_short: false,
    ma_long: false,
    bb: false,
    psar: false,
    ema_fast: false,
    ema_slow: false,
  });

  const [showPatterns, setShowPatterns] = useState(true);
  const [showCandles, setShowCandles] = useState(true);
  const [indicatorData, setIndicatorData] = useState(null);
  const [loading, setLoading] = useState(false);

  const toggleIndicator = (indicator) => {
    setSelectedIndicators(prev => ({
      ...prev,
      [indicator]: !prev[indicator]
    }));
  };

  // Fetch detailed indicator data
  useEffect(() => {
    if (!stockId || !indicatorParams) return;

    const fetchIndicatorData = async () => {
      setLoading(true);
      try {
        // Build query string with parameters
        const params = new URLSearchParams({
          days: '365',
          ...indicatorParams
        });
        const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/v1/stocks/${stockId}/indicators?${params}`);
        const data = await response.json();
        setIndicatorData(data);
      } catch (error) {
        console.error('Failed to fetch indicator data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchIndicatorData();
  }, [stockId, indicatorParams]);

  // Create chart and add candlestick data (only when prices change)
  useEffect(() => {
    if (!prices || prices.length === 0) return;
    if (!chartContainerRef.current) return;

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    seriesRefs.current = {};

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 500,
      layout: {
        backgroundColor: '#ffffff',
        textColor: '#333',
      },
      grid: {
        vertLines: {
          color: '#f0f0f0',
        },
        horzLines: {
          color: '#f0f0f0',
        },
      },
      crosshair: {
        mode: 1, // Normal crosshair
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
    });

    chartRef.current = chart;

    // Add candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderDownColor: '#ef5350',
      borderUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      wickUpColor: '#26a69a',
    });

    seriesRefs.current.candles = candleSeries;

    // Prepare chart data
    const sortedPrices = [...prices].sort((a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    const chartData = sortedPrices.map(price => ({
      time: Math.floor(new Date(price.timestamp).getTime() / 1000),
      open: parseFloat(price.open),
      high: parseFloat(price.high),
      low: parseFloat(price.low),
      close: parseFloat(price.close),
    }));

    candleSeries.setData(chartData);
    chart.timeScale().fitContent();

    // Handle window resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [prices]);

  // Control candlestick visibility and add line chart as alternative
  useEffect(() => {
    if (!chartRef.current) return;
    if (!seriesRefs.current.candles) return;

    const chart = chartRef.current;
    const candleSeries = seriesRefs.current.candles;

    if (showCandles) {
      // Show candlesticks, hide line chart
      candleSeries.applyOptions({ visible: true });

      // Remove line series if it exists
      if (seriesRefs.current.closeLine) {
        try {
          chart.removeSeries(seriesRefs.current.closeLine);
          delete seriesRefs.current.closeLine;
        } catch (e) {
          console.warn('Failed to remove close line:', e);
        }
      }
    } else {
      // Hide candlesticks, show line chart
      candleSeries.applyOptions({ visible: false });

      // Create line series for close prices if not exists
      if (!seriesRefs.current.closeLine && prices && prices.length > 0) {
        const lineSeries = chart.addLineSeries({
          color: '#2962FF',
          lineWidth: 2,
          title: 'Close Price',
          priceLineVisible: true,
          lastValueVisible: true,
        });

        const sortedPrices = [...prices].sort((a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

        const lineData = sortedPrices.map(price => ({
          time: Math.floor(new Date(price.timestamp).getTime() / 1000),
          value: parseFloat(price.close),
        }));

        lineSeries.setData(lineData);
        seriesRefs.current.closeLine = lineSeries;
      }
    }
  }, [showCandles, prices]);

  // Manage indicator overlays (when indicators are toggled or data changes)
  useEffect(() => {
    if (!chartRef.current || !indicatorData || !indicatorData.prices) return;

    const chart = chartRef.current;
    const indicatorChartData = indicatorData.prices.map(item => ({
      time: Math.floor(new Date(item.timestamp).getTime() / 1000),
      ...item
    }));

    // Helper function to remove a series safely
    const removeSeries = (seriesKey) => {
      if (seriesRefs.current[seriesKey]) {
        try {
          chart.removeSeries(seriesRefs.current[seriesKey]);
        } catch (e) {
          console.warn(`Failed to remove series ${seriesKey}:`, e);
        }
        delete seriesRefs.current[seriesKey];
      }
    };

    // Short Moving Average
    if (selectedIndicators.ma_short && indicatorData.prices.some(p => p.ma_short)) {
      if (!seriesRefs.current.ma_short) {
        seriesRefs.current.ma_short = chart.addLineSeries({
          color: '#2962FF',
          lineWidth: 2,
          title: 'MA Short',
        });
        const maShortData = indicatorChartData
          .filter(d => d.ma_short !== null && d.ma_short !== undefined)
          .map(d => ({ time: d.time, value: parseFloat(d.ma_short) }));
        seriesRefs.current.ma_short.setData(maShortData);
      }
    } else {
      removeSeries('ma_short');
    }

    // Long Moving Average
    if (selectedIndicators.ma_long && indicatorData.prices.some(p => p.ma_long)) {
      if (!seriesRefs.current.ma_long) {
        seriesRefs.current.ma_long = chart.addLineSeries({
          color: '#FF6D00',
          lineWidth: 2,
          title: 'MA Long',
        });
        const maLongData = indicatorChartData
          .filter(d => d.ma_long !== null && d.ma_long !== undefined)
          .map(d => ({ time: d.time, value: parseFloat(d.ma_long) }));
        seriesRefs.current.ma_long.setData(maLongData);
      }
    } else {
      removeSeries('ma_long');
    }

    // EMA Fast
    if (selectedIndicators.ema_fast && indicatorData.prices.some(p => p.ema_fast)) {
      if (!seriesRefs.current.ema_fast) {
        seriesRefs.current.ema_fast = chart.addLineSeries({
          color: '#00897B',
          lineWidth: 2,
          title: 'EMA Fast',
        });
        const emaFastData = indicatorChartData
          .filter(d => d.ema_fast !== null && d.ema_fast !== undefined)
          .map(d => ({ time: d.time, value: parseFloat(d.ema_fast) }));
        seriesRefs.current.ema_fast.setData(emaFastData);
      }
    } else {
      removeSeries('ema_fast');
    }

    // EMA Slow
    if (selectedIndicators.ema_slow && indicatorData.prices.some(p => p.ema_slow)) {
      if (!seriesRefs.current.ema_slow) {
        seriesRefs.current.ema_slow = chart.addLineSeries({
          color: '#D81B60',
          lineWidth: 2,
          title: 'EMA Slow',
        });
        const emaSlowData = indicatorChartData
          .filter(d => d.ema_slow !== null && d.ema_slow !== undefined)
          .map(d => ({ time: d.time, value: parseFloat(d.ema_slow) }));
        seriesRefs.current.ema_slow.setData(emaSlowData);
      }
    } else {
      removeSeries('ema_slow');
    }

    // Bollinger Bands
    if (selectedIndicators.bb && indicatorData.prices.some(p => p.bb_upper)) {
      // Upper Band
      if (!seriesRefs.current.bb_upper) {
        seriesRefs.current.bb_upper = chart.addLineSeries({
          color: 'rgba(41, 98, 255, 0.5)',
          lineWidth: 1,
          title: 'BB Upper',
        });
        const bbUpperData = indicatorChartData
          .filter(d => d.bb_upper !== null && d.bb_upper !== undefined)
          .map(d => ({ time: d.time, value: parseFloat(d.bb_upper) }));
        seriesRefs.current.bb_upper.setData(bbUpperData);
      }

      // Middle Band
      if (!seriesRefs.current.bb_middle) {
        seriesRefs.current.bb_middle = chart.addLineSeries({
          color: 'rgba(41, 98, 255, 0.8)',
          lineWidth: 1,
          lineStyle: 2, // Dashed
          title: 'BB Middle',
        });
        const bbMiddleData = indicatorChartData
          .filter(d => d.bb_middle !== null && d.bb_middle !== undefined)
          .map(d => ({ time: d.time, value: parseFloat(d.bb_middle) }));
        seriesRefs.current.bb_middle.setData(bbMiddleData);
      }

      // Lower Band
      if (!seriesRefs.current.bb_lower) {
        seriesRefs.current.bb_lower = chart.addLineSeries({
          color: 'rgba(41, 98, 255, 0.5)',
          lineWidth: 1,
          title: 'BB Lower',
        });
        const bbLowerData = indicatorChartData
          .filter(d => d.bb_lower !== null && d.bb_lower !== undefined)
          .map(d => ({ time: d.time, value: parseFloat(d.bb_lower) }));
        seriesRefs.current.bb_lower.setData(bbLowerData);
      }
    } else {
      removeSeries('bb_upper');
      removeSeries('bb_middle');
      removeSeries('bb_lower');
    }

    // Parabolic SAR
    if (selectedIndicators.psar && indicatorData.prices.some(p => p.psar)) {
      if (!seriesRefs.current.psar) {
        seriesRefs.current.psar = chart.addLineSeries({
          color: '#FFA726',
          lineWidth: 1,
          lineStyle: 0,
          pointMarkersVisible: true,
          title: 'Parabolic SAR',
        });
        const psarData = indicatorChartData
          .filter(d => d.psar !== null && d.psar !== undefined)
          .map(d => ({ time: d.time, value: parseFloat(d.psar) }));
        seriesRefs.current.psar.setData(psarData);
      }
    } else {
      removeSeries('psar');
    }
  }, [selectedIndicators, indicatorData]);

  // Add pattern markers to the chart
  useEffect(() => {
    if (!chartRef.current || !seriesRefs.current.candles) return;

    const candleSeries = seriesRefs.current.candles;

    // If patterns are disabled or empty, clear markers
    if (!showPatterns || !patterns || patterns.length === 0) {
      candleSeries.setMarkers([]);
      return;
    }

    // Convert patterns to markers
    const markers = patterns.map(pattern => {
      const timestamp = Math.floor(new Date(pattern.timestamp).getTime() / 1000);
      const isBullish = pattern.pattern_type === 'bullish';

      return {
        time: timestamp,
        position: isBullish ? 'belowBar' : 'aboveBar',
        color: isBullish ? '#28a745' : '#dc3545',
        shape: isBullish ? 'arrowUp' : 'arrowDown',
        text: pattern.pattern_name,
        size: 1,
      };
    });

    // Sort markers by time (ascending order required by TradingView)
    markers.sort((a, b) => a.time - b.time);

    // Set markers on candlestick series
    candleSeries.setMarkers(markers);

  }, [patterns, showPatterns]);

  // Draw chart pattern trendlines and markers
  useEffect(() => {
    console.log('[StockChart] Chart patterns received:', chartPatterns);
    if (!chartRef.current || !seriesRefs.current.candles) {
      console.log('[StockChart] Chart ref or candle series not available');
      return;
    }

    const chart = chartRef.current;
    const candleSeries = seriesRefs.current.candles;

    // Clear existing trendlines
    trendlineRefs.current.forEach(series => {
      try {
        chart.removeSeries(series);
      } catch (e) {
        console.warn('Failed to remove trendline:', e);
      }
    });
    trendlineRefs.current = [];

    // If no chart patterns, clear markers and return
    if (!chartPatterns || chartPatterns.length === 0) {
      console.log('[StockChart] No chart patterns to draw');
      // Clear pattern markers (keep candlestick pattern markers if they exist)
      if (patterns && patterns.length === 0) {
        candleSeries.setMarkers([]);
      }
      return;
    }

    console.log('[StockChart] Drawing patterns for', chartPatterns.length, 'patterns');

    // Collect all pattern markers (peaks, troughs, boundaries)
    const allMarkers = [];

    // Draw each visible chart pattern
    chartPatterns.forEach((pattern, patternIndex) => {
      console.log(`[StockChart] Processing pattern ${patternIndex}:`, pattern.pattern_name);

      // Enhanced color scheme for better visibility
      const getColor = (lineKey) => {
        // Bullish patterns: green tones
        if (pattern.signal === 'bullish') {
          if (lineKey.includes('support') || lineKey.includes('lower')) return '#10b981'; // Bright green
          if (lineKey.includes('resistance') || lineKey.includes('upper')) return '#059669'; // Dark green
          return '#14b8a6'; // Teal
        }
        // Bearish patterns: red tones
        if (pattern.signal === 'bearish') {
          if (lineKey.includes('resistance') || lineKey.includes('upper')) return '#ef4444'; // Bright red
          if (lineKey.includes('support') || lineKey.includes('lower')) return '#dc2626'; // Dark red
          return '#f59e0b'; // Orange
        }
        // Neutral patterns: blue/purple tones
        if (lineKey.includes('upper') || lineKey.includes('resistance')) return '#6366f1'; // Indigo
        if (lineKey.includes('lower') || lineKey.includes('support')) return '#8b5cf6'; // Purple
        return '#3b82f6'; // Blue
      };

      const primaryColor = pattern.signal === 'bullish' ? '#28a745' : pattern.signal === 'bearish' ? '#dc3545' : '#6c757d';

      // Draw peaks as markers if available - LARGER and MORE VISIBLE
      if (pattern.key_points?.peaks && Array.isArray(pattern.key_points.peaks)) {
        console.log(`[StockChart] Drawing ${pattern.key_points.peaks.length} peak markers`);
        pattern.key_points.peaks.forEach((peak, idx) => {
          allMarkers.push({
            time: Math.floor(new Date(peak.timestamp).getTime() / 1000),
            position: 'aboveBar',
            color: pattern.signal === 'bearish' ? '#dc3545' : '#f39c12',
            shape: 'circle',
            text: `Peak ${idx + 1}`,
            size: 2, // Much larger
          });
        });
      }

      // Draw troughs as markers if available - LARGER and MORE VISIBLE
      if (pattern.key_points?.troughs && Array.isArray(pattern.key_points.troughs)) {
        console.log(`[StockChart] Drawing ${pattern.key_points.troughs.length} trough markers`);
        pattern.key_points.troughs.forEach((trough, idx) => {
          allMarkers.push({
            time: Math.floor(new Date(trough.timestamp).getTime() / 1000),
            position: 'belowBar',
            color: pattern.signal === 'bullish' ? '#28a745' : '#f39c12',
            shape: 'circle',
            text: `Trough ${idx + 1}`,
            size: 2, // Much larger
          });
        });
      }

      // Add pattern boundary markers (start/end) - MUCH MORE PROMINENT
      const startTime = Math.floor(new Date(pattern.start_date).getTime() / 1000);
      const endTime = Math.floor(new Date(pattern.end_date).getTime() / 1000);

      allMarkers.push({
        time: startTime,
        position: 'aboveBar',
        color: primaryColor,
        shape: 'arrowDown',
        text: `${pattern.pattern_name} START`,
        size: 3, // Very large for visibility
      });

      allMarkers.push({
        time: endTime,
        position: 'aboveBar',
        color: primaryColor,
        shape: 'arrowDown',
        text: `${pattern.pattern_name} END`,
        size: 3, // Very large for visibility
      });

      // Draw trendlines if available
      if (pattern.trendlines) {
        console.log(`[StockChart] Pattern ${patternIndex} trendlines:`, Object.keys(pattern.trendlines));

        Object.entries(pattern.trendlines).forEach(([lineKey, lineData]) => {
          console.log(`[StockChart] Trendline ${lineKey} data:`, lineData);

          // Check if we have slope/intercept (linear regression format)
          if (!lineData || typeof lineData.slope === 'undefined' || typeof lineData.intercept === 'undefined') {
            console.log(`[StockChart] Skipping trendline ${lineKey}: missing slope/intercept`);
            return;
          }

          console.log(`[StockChart] Drawing trendline ${lineKey} with slope=${lineData.slope}, intercept=${lineData.intercept}`);

          // Generate points from slope and intercept
          // y = slope * x + intercept, where x is the day index from start_date
          const startDate = new Date(pattern.start_date);
          const endDate = new Date(pattern.end_date);
          const daysDiff = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24));

          const trendlineData = [];

          // Generate points for each day in the pattern range
          for (let dayIndex = 0; dayIndex <= daysDiff; dayIndex++) {
            const currentDate = new Date(startDate);
            currentDate.setDate(currentDate.getDate() + dayIndex);

            const price = lineData.slope * dayIndex + lineData.intercept;

            trendlineData.push({
              time: Math.floor(currentDate.getTime() / 1000),
              value: parseFloat(price.toFixed(2))
            });
          }

          console.log(`[StockChart] Generated ${trendlineData.length} points for trendline ${lineKey}`);

          // Create line series for this trendline with enhanced visibility
          const lineStyle = lineKey.includes('support') || lineKey.includes('lower') ? 2 : 0; // Dashed for support, solid for resistance
          const trendlineSeries = chart.addLineSeries({
            color: getColor(lineKey),
            lineWidth: 3, // Thicker lines for better visibility
            lineStyle: lineStyle, // 0=solid, 1=dotted, 2=dashed
            title: `${pattern.pattern_name} - ${lineKey}`,
            priceLineVisible: false,
            lastValueVisible: false,
          });

          trendlineSeries.setData(trendlineData);
          trendlineRefs.current.push(trendlineSeries);
          console.log(`[StockChart] Successfully drew trendline ${lineKey}`);
        });
      }
    });

    // Set all markers on candlestick series
    if (allMarkers.length > 0) {
      allMarkers.sort((a, b) => a.time - b.time);
      candleSeries.setMarkers(allMarkers);
      console.log(`[StockChart] Set ${allMarkers.length} total markers`);
    }

  }, [chartPatterns, patterns]);

  // Add visual highlight for hovered pattern - zoom to pattern with padding
  useEffect(() => {
    if (!chartRef.current || !prices || prices.length === 0) return;

    const chart = chartRef.current;

    // If no pattern is highlighted, reset to full view
    if (!highlightedPattern) {
      chart.timeScale().fitContent();
      return;
    }

    // Zoom to the highlighted pattern's time range with generous padding
    const startDate = new Date(highlightedPattern.start_date);
    const endDate = new Date(highlightedPattern.end_date);

    // Calculate pattern duration to determine appropriate padding
    const patternDurationDays = (endDate - startDate) / (1000 * 60 * 60 * 24);

    // Use 30% of pattern duration as padding, minimum 7 days
    const paddingDays = Math.max(7, Math.ceil(patternDurationDays * 0.3));
    const paddingSeconds = paddingDays * 24 * 60 * 60;

    chart.timeScale().setVisibleRange({
      from: Math.floor(startDate.getTime() / 1000) - paddingSeconds,
      to: Math.floor(endDate.getTime() / 1000) + paddingSeconds,
    });

  }, [highlightedPattern, prices]);

  return (
    <div className="stock-chart">
      <div className="chart-header">
        <h3>{symbol} Price History</h3>
        {loading && <span className="loading-badge">Loading indicators...</span>}
      </div>

      {/* Indicator Controls */}
      <div className="indicator-controls">
        <div className="controls-title">📊 Chart Overlays</div>
        <div className="controls-grid">
          {/* Candlestick Toggle */}
          <label className="control-item candle-control">
            <input
              type="checkbox"
              checked={showCandles}
              onChange={() => setShowCandles(!showCandles)}
            />
            <span className="indicator-color" style={{ backgroundColor: showCandles ? '#26a69a' : '#2962FF' }}></span>
            <span>{showCandles ? 'Candlesticks (OHLC)' : 'Close Price Line'}</span>
          </label>

          {/* Pattern Markers Toggle */}
          <label className="control-item pattern-control">
            <input
              type="checkbox"
              checked={showPatterns}
              onChange={() => setShowPatterns(!showPatterns)}
            />
            <span className="indicator-color" style={{ backgroundColor: patterns?.length > 0 ? '#764ba2' : '#ccc' }}></span>
            <span>Pattern Markers {patterns?.length > 0 ? `(${patterns.length})` : ''}</span>
          </label>

          <label className="control-item">
            <input
              type="checkbox"
              checked={selectedIndicators.ma_short}
              onChange={() => toggleIndicator('ma_short')}
            />
            <span className="indicator-color" style={{ backgroundColor: '#2962FF' }}></span>
            <span>MA Short (20)</span>
          </label>

          <label className="control-item">
            <input
              type="checkbox"
              checked={selectedIndicators.ma_long}
              onChange={() => toggleIndicator('ma_long')}
            />
            <span className="indicator-color" style={{ backgroundColor: '#FF6D00' }}></span>
            <span>MA Long (50)</span>
          </label>

          <label className="control-item">
            <input
              type="checkbox"
              checked={selectedIndicators.ema_fast}
              onChange={() => toggleIndicator('ema_fast')}
            />
            <span className="indicator-color" style={{ backgroundColor: '#00897B' }}></span>
            <span>EMA Fast (12)</span>
          </label>

          <label className="control-item">
            <input
              type="checkbox"
              checked={selectedIndicators.ema_slow}
              onChange={() => toggleIndicator('ema_slow')}
            />
            <span className="indicator-color" style={{ backgroundColor: '#D81B60' }}></span>
            <span>EMA Slow (26)</span>
          </label>

          <label className="control-item">
            <input
              type="checkbox"
              checked={selectedIndicators.bb}
              onChange={() => toggleIndicator('bb')}
            />
            <span className="indicator-color" style={{ backgroundColor: 'rgba(41, 98, 255, 0.5)' }}></span>
            <span>Bollinger Bands</span>
          </label>

          <label className="control-item">
            <input
              type="checkbox"
              checked={selectedIndicators.psar}
              onChange={() => toggleIndicator('psar')}
            />
            <span className="indicator-color" style={{ backgroundColor: '#FFA726' }}></span>
            <span>Parabolic SAR</span>
          </label>
        </div>
      </div>

      <div ref={chartContainerRef} className="chart-container" />

      <style jsx>{`
        .stock-chart {
          margin: 20px 0;
          background: white;
          border-radius: 8px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .chart-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 15px;
        }

        .chart-header h3 {
          margin: 0;
          color: #333;
          font-size: 20px;
        }

        .loading-badge {
          background: #e7f3ff;
          color: #004085;
          padding: 4px 12px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 500;
        }

        .indicator-controls {
          background: #f8f9fa;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 15px;
          margin-bottom: 20px;
        }

        .controls-title {
          font-size: 14px;
          font-weight: 600;
          color: #333;
          margin-bottom: 12px;
        }

        .controls-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 12px;
        }

        .control-item {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          padding: 8px;
          background: white;
          border-radius: 6px;
          border: 1px solid #e5e7eb;
          transition: all 0.2s;
        }

        .control-item:hover {
          background: #f0f0f0;
          border-color: #667eea;
        }

        .control-item input[type="checkbox"] {
          cursor: pointer;
          width: 16px;
          height: 16px;
        }

        .indicator-color {
          width: 20px;
          height: 3px;
          border-radius: 2px;
        }

        .control-item span {
          font-size: 13px;
          color: #333;
          font-weight: 500;
        }

        .candle-control {
          border: 2px solid #26a69a;
          background: linear-gradient(135deg, #e0f7f5 0%, #f0fffe 100%);
        }

        .candle-control:hover {
          background: linear-gradient(135deg, #d0f2ef 0%, #e8fcfa 100%);
          border-color: #1e8e85;
        }

        .pattern-control {
          border: 2px solid #764ba2;
          background: linear-gradient(135deg, #ffeef8 0%, #fff5fb 100%);
        }

        .pattern-control:hover {
          background: linear-gradient(135deg, #ffe5f5 0%, #fff0f8 100%);
          border-color: #5a3678;
        }

        .chart-container {
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          overflow: hidden;
        }
      `}</style>
    </div>
  );
});

export default StockChart;
