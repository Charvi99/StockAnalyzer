import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health check
export const checkHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

// Stock endpoints
export const getStocks = async (trackedOnly = true) => {
  const response = await api.get('/api/v1/stocks/', {
    params: { tracked_only: trackedOnly }
  });
  return response.data;
};

export const getStock = async (stockId) => {
  const response = await api.get(`/api/v1/stocks/${stockId}`);
  return response.data;
};

export const getStockBySymbol = async (symbol) => {
  const response = await api.get(`/api/v1/stocks/symbol/${symbol}`);
  return response.data;
};

export const createStock = async (stockData) => {
  const response = await api.post('/api/v1/stocks/', stockData);
  return response.data;
};

export const updateStock = async (stockId, stockData) => {
  const response = await api.patch(`/api/v1/stocks/${stockId}`, stockData);
  return response.data;
};

export const deleteStock = async (stockId) => {
  const response = await api.delete(`/api/v1/stocks/${stockId}`);
  return response.data;
};

// Stock Price endpoints
export const fetchStockData = async (stockId, period = '1y', interval = '1d') => {
  const response = await api.post(`/api/v1/stocks/${stockId}/fetch`, {
    period,
    interval
  });
  return response.data;
};

export const getStockPrices = async (stockId, limit = 100, skip = 0) => {
  const response = await api.get(`/api/v1/stocks/${stockId}/prices`, {
    params: { limit, skip }
  });
  return response.data;
};

export const getStockPricesBySymbol = async (symbol, limit = 100, skip = 0) => {
  const response = await api.get(`/api/v1/stocks/symbol/${symbol}/prices`, {
    params: { limit, skip }
  });
  return response.data;
};

export const getLatestPrice = async (stockId) => {
  const response = await api.get(`/api/v1/stocks/${stockId}/latest`);
  return response.data;
};

export const deleteStockPrices = async (stockId) => {
  const response = await api.delete(`/api/v1/stocks/${stockId}/prices`);
  return response.data;
};

// Analysis endpoints
export const getRecommendation = async (stockId) => {
  const response = await api.get(`/api/v1/stocks/${stockId}/recommendation`);
  return response.data;
};

export const analyzeComplete = async (stockId) => {
  const response = await api.post(`/api/v1/stocks/${stockId}/analyze-complete`);
  return response.data;
};

export const analyzeTechnical = async (stockId, params = {}) => {
  const response = await api.post(`/api/v1/stocks/${stockId}/analyze`, params);
  return response.data;
};

export const getPredictions = async (stockId, limit = 10) => {
  const response = await api.get(`/api/v1/stocks/${stockId}/predictions`, {
    params: { limit }
  });
  return response.data;
};

// ML endpoints (Phase 4)
export const trainMLModel = async (stockId, params) => {
  const response = await api.post(`/api/v1/ml/stocks/${stockId}/train`, params);
  return response.data;
};

export const predictML = async (stockId, params) => {
  const response = await api.post(`/api/v1/ml/stocks/${stockId}/predict`, params);
  return response.data;
};

export const getMLModels = async () => {
  const response = await api.get('/api/v1/ml/models');
  return response.data;
};

// Sentiment endpoints (Phase 4)
export const analyzeSentiment = async (stockId, params = {}) => {
  const response = await api.post(`/api/v1/sentiment/stocks/${stockId}/analyze`, params);
  return response.data;
};

export const getSentimentHistory = async (stockId, limit = 10) => {
  const response = await api.get(`/api/v1/sentiment/stocks/${stockId}/history`, {
    params: { limit }
  });
  return response.data;
};

export const getLatestSentiment = async (stockId) => {
  const response = await api.get(`/api/v1/sentiment/stocks/${stockId}/latest`);
  return response.data;
};

export const getDashboardAnalysis = async () => {
  const response = await api.get('/api/v1/analysis/dashboard');
  return response.data;
};

// Candlestick Pattern endpoints (Phase 5)
export const detectPatterns = async (stockId, days = 90) => {
  const response = await api.post(`/api/v1/stocks/${stockId}/detect-patterns`, { days });
  return response.data;
};

export const getPatterns = async (stockId, params = {}) => {
  const response = await api.get(`/api/v1/stocks/${stockId}/patterns`, { params });
  return response.data;
};

export const confirmPattern = async (patternId, confirmed, notes = '', confirmedBy = 'user') => {
  const response = await api.patch(`/api/v1/patterns/${patternId}/confirm`, {
    confirmed,
    notes,
    confirmed_by: confirmedBy
  });
  return response.data;
};

export const deletePattern = async (patternId) => {
  const response = await api.delete(`/api/v1/patterns/${patternId}`);
  return response.data;
};

export const getPatternStats = async (stockId = null) => {
  const params = stockId ? { stock_id: stockId } : {};
  const response = await api.get('/api/v1/patterns/stats', { params });
  return response.data;
};

// Chart Pattern endpoints (Phase 6)
export const detectChartPatterns = async (
  stockId,
  days = null,
  minPatternLength = 20,
  removeOverlaps = true,
  excludePatterns = null,
  overlapThreshold = 0.1,
  peakOrder = 5,
  minConfidence = 0.0,
  minRSquared = 0.0
) => {
  const payload = {
    min_pattern_length: minPatternLength,
    remove_overlaps: removeOverlaps,
    overlap_threshold: overlapThreshold,
    peak_order: peakOrder,
    min_confidence: minConfidence,
    min_r_squared: minRSquared
  };

  // Only include days if it's specified
  if (days !== null && days !== undefined) {
    payload.days = days;
  }

  // Include exclude_patterns if specified
  if (excludePatterns && excludePatterns.length > 0) {
    payload.exclude_patterns = excludePatterns;
  }

  const response = await api.post(`/api/v1/stocks/${stockId}/detect-chart-patterns`, payload);
  return response.data;
};

export const getChartPatterns = async (stockId, params = {}) => {
  const response = await api.get(`/api/v1/stocks/${stockId}/chart-patterns`, { params });
  return response.data;
};

export const confirmChartPattern = async (patternId, confirmed, notes = '', confirmedBy = 'user') => {
  const response = await api.patch(`/api/v1/chart-patterns/${patternId}/confirm`, {
    confirmed,
    notes,
    confirmed_by: confirmedBy
  });
  return response.data;
};

export const deleteChartPattern = async (patternId) => {
  const response = await api.delete(`/api/v1/chart-patterns/${patternId}`);
  return response.data;
};

export const getChartPatternStats = async (stockId = null) => {
  const params = stockId ? { stock_id: stockId } : {};
  const response = await api.get('/api/v1/chart-patterns/stats', { params });
  return response.data;
};

export const exportChartPatternTrainingData = async (confirmedOnly = true, stockId = null) => {
  const params = { confirmed_only: confirmedOnly };
  if (stockId) params.stock_id = stockId;
  const response = await api.get('/api/v1/chart-patterns/export/training-data', { params });
  return response.data;
};

// Trading Strategy endpoints (Phase 6)
export const listStrategies = async () => {
  const response = await api.get('/api/v1/strategies/list');
  return response.data;
};

export const getStrategyDetails = async (strategyName) => {
  const response = await api.get(`/api/v1/strategies/${strategyName}`);
  return response.data;
};

export const executeStrategy = async (stockId, params) => {
  const response = await api.post(`/api/v1/strategies/${stockId}/execute`, params);
  return response.data;
};

export const backtestStrategy = async (stockId, params) => {
  const response = await api.post(`/api/v1/strategies/${stockId}/backtest`, params);
  return response.data;
};

export const executeAllStrategies = async (stockId) => {
  const response = await api.post(`/api/v1/strategies/${stockId}/execute-all`);
  return response.data;
};

export default api;
