import React, { useMemo } from 'react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const SignalRadar = ({ recommendation }) => {
  // Memoize processed data to prevent unnecessary recalculations
  const radarData = useMemo(() => {
    if (!recommendation) return null;

    const processSignal = (signal, confidence) => {
      if (signal === 'BUY') return confidence * 100;
      if (signal === 'SELL') return confidence * -100;
      return 0;
    };

    // Sentiment score is already on -100 to +100 scale
    const sentimentScore = recommendation.sentiment_index || 0;

    const data = [
      {
        factor: 'Technical',
        value: processSignal(recommendation.technical_recommendation, recommendation.technical_confidence),
      },
      {
        factor: 'ML',
        value: processSignal(recommendation.ml_recommendation, recommendation.ml_confidence),
      },
      {
        factor: 'Sentiment',
        value: sentimentScore,
      },
      {
        factor: 'Candlestick',
        value: processSignal(recommendation.candlestick_signal, recommendation.candlestick_confidence),
      },
      {
        factor: 'Chart Pattern',
        value: processSignal(recommendation.chart_pattern_signal, recommendation.chart_pattern_confidence),
      },
      {
        // Phase 0.5: aggregated vote across the registered trading strategies.
        factor: 'Strategies',
        value: processSignal(
          recommendation.strategy_consensus_signal,
          recommendation.strategy_consensus_confidence
        ),
      },
      // 'Overall' is intentionally NOT a radar axis: it is the *combined*
      // recommendation (shown as the header badge below). Plotting it as an axis
      // made the polygon's overall reach just duplicate the Technical axis.
      // (user issue #3)
    ];

    return data.map(item => ({ ...item, normalizedValue: item.value + 100 }));
  }, [recommendation]);

  const thresholdData = useMemo(() => {
    if (!radarData) return null;

    return radarData.map(item => ({
      ...item,
      buyThreshold: 170, // 70 + 100
      sellThreshold: 30, // -70 + 100
      holdThreshold: 100, // 0 + 100
    }));
  }, [radarData]);

  if (!recommendation || !radarData || !thresholdData) {
    return <div className="no-data">No recommendation data available</div>;
  }

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="radar-tooltip">
          <p className="label"><strong>{data.factor}</strong></p>
          <p>Score: {data.value.toFixed(2)}</p>
        </div>
      );
    }
    return null;
  };

  const finalColor = recommendation.final_recommendation === 'BUY' ? '#26a69a' : recommendation.final_recommendation === 'SELL' ? '#ef5350' : '#f59e0b';

  return (
    <div className="signal-radar">
      <div className="radar-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ margin: 0 }}>Signal Strength Analysis</h3>
        <div className="overall-badge" title="Combined recommendation across all factors" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 10, border: `2px solid ${finalColor}`, background: finalColor + '20' }}>
          <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.5px', color: '#6b7280' }}>OVERALL</span>
          <span style={{ fontSize: 20, fontWeight: 800, color: finalColor }}>{recommendation.final_recommendation}</span>
          <span style={{ fontSize: 12, color: '#6b7280' }}>{((recommendation.overall_confidence || 0) * 100).toFixed(0)}%</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={400}>
        <RadarChart cx="50%" cy="50%" outerRadius="80%" data={thresholdData}>
          <PolarGrid />
          <PolarAngleAxis dataKey="factor" />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 200]}
            ticks={[0, 30, 100, 170, 200]}
            tickFormatter={(value) => value - 100}
          />
          <Radar name="Buy Threshold" dataKey="buyThreshold" stroke="#26a69a" fill="none" strokeWidth={2} strokeDasharray="5 5" dot={false} />
          <Radar name="Sell Threshold" dataKey="sellThreshold" stroke="#ef5350" fill="none" strokeWidth={2} strokeDasharray="5 5" dot={false} />
          <Radar name="Hold Threshold" dataKey="holdThreshold" stroke="#f59e0b" fill="none" strokeWidth={1} strokeDasharray="5 5" dot={false} />
          <Radar
            name="Signal Strength"
            dataKey="normalizedValue"
            stroke={finalColor}
            fill={finalColor}
            fillOpacity={0.6}
            connectNulls
            dot={{ stroke: finalColor, strokeWidth: 2, r: 4 }}
            data={radarData}
          />
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default SignalRadar;