-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Stocks table - stores information about tracked stocks
CREATE TABLE IF NOT EXISTS stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255),
    sector VARCHAR(100),
    industry VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Historical stock data - time-series data
CREATE TABLE IF NOT EXISTS stock_prices (
    id SERIAL,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(12, 4),
    high DECIMAL(12, 4),
    low DECIMAL(12, 4),
    close DECIMAL(12, 4),
    volume BIGINT,
    adjusted_close DECIMAL(12, 4),
    PRIMARY KEY (stock_id, timestamp)
);

-- Convert stock_prices to a hypertable for time-series optimization
SELECT create_hypertable('stock_prices', 'timestamp', if_not_exists => TRUE);

-- Predictions table - stores ML model predictions
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    prediction_date TIMESTAMP NOT NULL,
    target_date TIMESTAMP NOT NULL,
    predicted_price DECIMAL(12, 4),
    predicted_change_percent DECIMAL(8, 4),
    confidence_score DECIMAL(5, 4),
    model_version VARCHAR(50),
    recommendation VARCHAR(10) CHECK (recommendation IN ('BUY', 'SELL', 'HOLD')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance tracking - compares predictions with actual results
CREATE TABLE IF NOT EXISTS prediction_performance (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES predictions(id) ON DELETE CASCADE,
    actual_price DECIMAL(12, 4),
    actual_change_percent DECIMAL(8, 4),
    prediction_error DECIMAL(12, 4),
    accuracy_score DECIMAL(5, 4),
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Technical indicators table (for future use)
CREATE TABLE IF NOT EXISTS technical_indicators (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    indicator_name VARCHAR(50) NOT NULL,
    value DECIMAL(12, 4),
    UNIQUE(stock_id, timestamp, indicator_name)
);

-- Sentiment scores table - stores news sentiment analysis results
CREATE TABLE IF NOT EXISTS sentiment_scores (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    sentiment_index DECIMAL(8, 4),
    positive_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    positive_pct DECIMAL(5, 2),
    negative_pct DECIMAL(5, 2),
    neutral_pct DECIMAL(5, 2),
    total_articles INTEGER DEFAULT 0,
    trend VARCHAR(20) CHECK (trend IN ('Rise', 'Fall', 'Neutral')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_stock_prices_stock_id ON stock_prices(stock_id);
CREATE INDEX IF NOT EXISTS idx_stock_prices_timestamp ON stock_prices(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_stock_id ON predictions(stock_id);
CREATE INDEX IF NOT EXISTS idx_predictions_target_date ON predictions(target_date);
CREATE INDEX IF NOT EXISTS idx_technical_indicators_stock_timestamp ON technical_indicators(stock_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sentiment_scores_stock_id ON sentiment_scores(stock_id);
CREATE INDEX IF NOT EXISTS idx_sentiment_scores_timestamp ON sentiment_scores(timestamp DESC);

-- Insert some sample stocks for testing
INSERT INTO stocks (symbol, name, sector, industry) VALUES
    ('AAPL', 'Apple Inc.', 'Technology', 'Consumer Electronics'),
    ('GOOGL', 'Alphabet Inc.', 'Technology', 'Internet Services'),
    ('MSFT', 'Microsoft Corporation', 'Technology', 'Software'),
    ('TSLA', 'Tesla, Inc.', 'Automotive', 'Electric Vehicles'),
    ('AMZN', 'Amazon.com Inc.', 'Consumer Cyclical', 'E-commerce')
ON CONFLICT (symbol) DO NOTHING;

-- Create a view for easy access to latest stock prices
CREATE OR REPLACE VIEW latest_stock_prices AS
SELECT DISTINCT ON (s.id)
    s.id,
    s.symbol,
    s.name,
    sp.timestamp,
    sp.close,
    sp.volume
FROM stocks s
LEFT JOIN stock_prices sp ON s.id = sp.stock_id
ORDER BY s.id, sp.timestamp DESC;

COMMENT ON TABLE stocks IS 'Stores information about tracked stocks';
COMMENT ON TABLE stock_prices IS 'Time-series data for stock prices (using TimescaleDB)';
COMMENT ON TABLE predictions IS 'ML model predictions for stock prices';
COMMENT ON TABLE prediction_performance IS 'Tracks accuracy of predictions vs actual results';
COMMENT ON TABLE technical_indicators IS 'Stores calculated technical indicator values';
COMMENT ON TABLE sentiment_scores IS 'Stores news sentiment analysis results using FinBERT';
