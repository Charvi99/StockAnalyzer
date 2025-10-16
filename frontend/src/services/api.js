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

export default api;
