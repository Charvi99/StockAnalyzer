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
        factor: 'Overall',
        value: processSignal(recommendation.final_recommendation, recommendation.overall_confidence),
      },
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
      <h3>Signal Strength Analysis</h3>
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