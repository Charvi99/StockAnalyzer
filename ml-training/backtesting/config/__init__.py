"""
Backtesting Configuration

All parameters for backtesting simulation.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict
from pathlib import Path


@dataclass
class TransactionCosts:
    """Transaction cost configuration"""
    commission_per_share: float = 0.0035  # $0.0035 per share
    eec_fee_remove: float = 0.0025  # ECN fee when removing liquidity
    eec_fee_add: float = -0.0020  # ECN rebate when adding liquidity
    sec_fee: float = 0.0000081  # SEC fee (selling only)
    finra_taf: float = 0.000119  # FINRA TAF (selling only)

    @property
    def total_round_trip(self) -> float:
        """Approximate total cost per round trip trade"""
        return (self.commission_per_share * 2 +
                self.eec_fee_remove +
                self.sec_fee +
                self.finra_taf)


@dataclass
class SlippageConfig:
    """Slippage configuration"""
    base_slippage: float = 0.0005  # 0.05% for liquid stocks
    illiquid_slippage: float = 0.0020  # 0.20% for illiquid stocks
    min_daily_volume: int = 1_000_000  # Below this = illiquid
    min_dollar_volume: int = 5_000_000  # Below this = illiquid

    # Advanced slippage (optional)
    volume_impact_factor: float = 0.001  # Impact per 1% of ADV
    volatility_impact_factor: float = 0.5  # Impact per volatility point


@dataclass
class UniverseConfig:
    """Stock universe configuration"""
    min_price: float = 5.0  # Minimum stock price
    min_daily_volume: int = 100_000  # Minimum daily volume
    min_dollar_volume: int = 1_000_000  # Minimum dollar volume
    max_positions: int = 20  # Maximum concurrent positions
    max_position_pct: float = 0.10  # Max 10% per position


@dataclass
class BacktestPeriod:
    """Backtest time period"""
    train_start: str  # Training start date (YYYY-MM-DD)
    train_end: str  # Training end date
    test_start: str  # Test start date (out-of-sample)
    test_end: str  # Test end date

    @property
    def train_years(self) -> float:
        """Training period in years"""
        # Simple calculation
        start = self.train_start.split('-')
        end = self.train_end.split('-')
        return (int(end[0]) - int(start[0])) + (int(end[1]) - int(start[1])) / 12


@dataclass
class BinaryExitConfig:
    """Exit rules for binary classification strategy"""
    profit_target: float = 0.03  # +3% profit target
    stop_loss: float = -0.02  # -2% stop loss
    max_hold_days: int = 20  # Maximum holding period

    def should_exit(self, pnl: float, days_held: int) -> tuple[bool, str]:
        """
        Check if position should be exited

        Returns:
            (should_exit, reason)
        """
        if pnl >= self.profit_target:
            return True, "profit_target"
        elif pnl <= self.stop_loss:
            return True, "stop_loss"
        elif days_held >= self.max_hold_days:
            return True, "time_exit"
        return False, ""


@dataclass
class BacktestConfig:
    """Main backtesting configuration"""

    # Data paths
    data_dir: Path = field(default_factory=lambda: Path("/app/outputs/features"))
    models_dir: Path = field(default_factory=lambda: Path("/app/outputs/models"))
    output_dir: Path = field(default_factory=lambda: Path("/app/outputs/features/backtests"))
    plots_dir: Path = field(default_factory=lambda: Path("/app/outputs/features/plots"))

    # Simulation
    initial_cash: float = 100_000  # Starting portfolio value
    costs: TransactionCosts = field(default_factory=TransactionCosts)
    slippage: SlippageConfig = field(default_factory=SlippageConfig)
    universe: UniverseConfig = field(default_factory=UniverseConfig)

    # Time period
    period: BacktestPeriod = field(default_factory=lambda: BacktestPeriod(
        train_start="2022-01-01",
        train_end="2024-01-01",
        test_start="2024-01-01",
        test_end="2025-01-01"
    ))

    # Binary strategy
    binary_exit: BinaryExitConfig = field(default_factory=BinaryExitConfig)

    # Reporting
    generate_html: bool = True  # Generate interactive HTML reports
    generate_png: bool = True  # Generate static PNG plots

    # Advanced options
    include_short_selling: bool = False  # Enable short selling
    include_dividends: bool = False  # Include dividend payments
    verbose: bool = True  # Verbose logging

    def to_dict(self) -> dict:
        """Convert to dictionary for saving"""
        from dataclasses import asdict

        def convert_value(obj):
            """Convert non-serializable objects"""
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, date):
                return obj.isoformat()
            return obj

        # Convert dataclass to dict
        result = asdict(self)

        # Handle nested objects
        for key, value in result.items():
            if isinstance(value, Path):
                result[key] = str(value)
            elif isinstance(value, BacktestPeriod):
                result[key] = {
                    'train_start': value.train_start,
                    'train_end': value.train_end,
                    'test_start': value.test_start,
                    'test_end': value.test_end,
                }
            elif isinstance(value, BinaryExitConfig):
                result[key] = {
                    'profit_target': value.profit_target,
                    'stop_loss': value.stop_loss,
                    'max_hold_days': value.max_hold_days,
                }

        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'BacktestConfig':
        """Create from dictionary"""
        return cls(**data)

    def save(self, path: Path):
        """Save config to file"""
        import json
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> 'BacktestConfig':
        """Load config from file"""
        import json
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)


# Default configuration instance
DEFAULT_CONFIG = BacktestConfig()
