import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

const StockChart = ({ prices, symbol }) => {
  const chartContainerRef = useRef();

  useEffect(() => {
    if (!prices || prices.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 400,
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
        mode: 'normal',
      },
      timeScale: {
        borderColor: '#cccccc',
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderDownColor: '#ef5350',
      borderUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      wickUpColor: '#26a69a',
    });

    const chartData = [...prices].reverse().map(price => ({
      time: new Date(price.timestamp).getTime() / 1000,
      open: parseFloat(price.open),
      high: parseFloat(price.high),
      low: parseFloat(price.low),
      close: parseFloat(price.close),
    }));

    candleSeries.setData(chartData);

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
    };
  }, [prices]);

  return (
    <div className="stock-chart">
      <h3>{symbol} Price History</h3>
      <div ref={chartContainerRef} />
    </div>
  );
};

export default StockChart;