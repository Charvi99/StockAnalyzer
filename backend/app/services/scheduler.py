"""
Scheduler service for automated prediction performance evaluation
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from app.db.database import SessionLocal
from app.models.stock import Prediction, PredictionPerformance, StockPrice

logger = logging.getLogger(__name__)


class PredictionEvaluationScheduler:
    """Scheduler for evaluating prediction accuracy"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("Prediction evaluation scheduler started")

    def evaluate_predictions(self):
        """
        Evaluate predictions that have reached their target date
        Compare predicted prices with actual prices
        """
        db: Session = SessionLocal()

        try:
            logger.info("Starting prediction evaluation job...")

            # Get predictions that haven't been evaluated yet
            unevaluated_predictions = db.query(Prediction).filter(
                Prediction.target_date <= datetime.utcnow(),
                ~Prediction.performance.any()
            ).all()

            evaluated_count = 0

            for prediction in unevaluated_predictions:
                try:
                    # Find actual price at target date
                    actual_price_record = db.query(StockPrice).filter(
                        and_(
                            StockPrice.stock_id == prediction.stock_id,
                            StockPrice.timestamp >= prediction.target_date,
                            StockPrice.timestamp <= prediction.target_date + timedelta(days=1)
                        )
                    ).first()

                    if not actual_price_record:
                        # Try to find the closest price within 3 days
                        actual_price_record = db.query(StockPrice).filter(
                            and_(
                                StockPrice.stock_id == prediction.stock_id,
                                StockPrice.timestamp >= prediction.target_date,
                                StockPrice.timestamp <= prediction.target_date + timedelta(days=3)
                            )
                        ).first()

                    if actual_price_record:
                        actual_price = float(actual_price_record.close)
                        predicted_price = float(prediction.predicted_price)

                        # Calculate actual change
                        base_price_record = db.query(StockPrice).filter(
                            and_(
                                StockPrice.stock_id == prediction.stock_id,
                                StockPrice.timestamp <= prediction.prediction_date
                            )
                        ).order_by(StockPrice.timestamp.desc()).first()

                        if base_price_record:
                            base_price = float(base_price_record.close)
                            actual_change_percent = ((actual_price - base_price) / base_price) * 100
                        else:
                            actual_change_percent = 0.0

                        # Calculate prediction error
                        prediction_error = abs(predicted_price - actual_price)
                        error_percent = (prediction_error / actual_price) * 100

                        # Calculate accuracy score (inverse of error, scaled to 0-1)
                        # 0% error = 1.0 accuracy, 10% error = 0.0 accuracy
                        accuracy_score = max(0.0, 1.0 - (error_percent / 10.0))

                        # Create performance record
                        performance = PredictionPerformance(
                            prediction_id=prediction.id,
                            actual_price=Decimal(str(actual_price)),
                            actual_change_percent=Decimal(str(actual_change_percent)),
                            prediction_error=Decimal(str(prediction_error)),
                            accuracy_score=Decimal(str(accuracy_score))
                        )

                        db.add(performance)
                        evaluated_count += 1

                        logger.info(
                            f"Evaluated prediction {prediction.id}: "
                            f"Predicted={predicted_price:.2f}, "
                            f"Actual={actual_price:.2f}, "
                            f"Error={prediction_error:.2f}, "
                            f"Accuracy={accuracy_score:.2f}"
                        )

                except Exception as e:
                    logger.error(f"Error evaluating prediction {prediction.id}: {str(e)}")
                    continue

            db.commit()
            logger.info(f"Prediction evaluation completed. Evaluated {evaluated_count} predictions.")

        except Exception as e:
            logger.error(f"Prediction evaluation job failed: {str(e)}")
            db.rollback()
        finally:
            db.close()

    def schedule_daily_evaluation(self):
        """Schedule daily evaluation at midnight"""
        self.scheduler.add_job(
            self.evaluate_predictions,
            trigger=CronTrigger(hour=0, minute=0),
            id="daily_prediction_evaluation",
            name="Evaluate predictions daily at midnight",
            replace_existing=True
        )
        logger.info("Scheduled daily prediction evaluation at midnight")

    def schedule_hourly_evaluation(self):
        """Schedule hourly evaluation"""
        self.scheduler.add_job(
            self.evaluate_predictions,
            trigger=CronTrigger(hour="*", minute=0),
            id="hourly_prediction_evaluation",
            name="Evaluate predictions every hour",
            replace_existing=True
        )
        logger.info("Scheduled hourly prediction evaluation")

    def run_evaluation_now(self):
        """Run evaluation immediately (for testing)"""
        self.evaluate_predictions()

    def shutdown(self):
        """Shutdown the scheduler"""
        self.scheduler.shutdown()
        logger.info("Prediction evaluation scheduler shutdown")


# Global scheduler instance
prediction_scheduler = None


def init_scheduler(schedule_type: str = "daily"):
    """
    Initialize the prediction evaluation scheduler

    Args:
        schedule_type: "daily", "hourly", or "none"
    """
    global prediction_scheduler

    if prediction_scheduler is not None:
        logger.warning("Scheduler already initialized")
        return prediction_scheduler

    prediction_scheduler = PredictionEvaluationScheduler()

    if schedule_type == "daily":
        prediction_scheduler.schedule_daily_evaluation()
    elif schedule_type == "hourly":
        prediction_scheduler.schedule_hourly_evaluation()
    elif schedule_type == "none":
        logger.info("Scheduler initialized but not scheduled to run automatically")
    else:
        raise ValueError(f"Invalid schedule_type: {schedule_type}")

    return prediction_scheduler


def get_scheduler() -> PredictionEvaluationScheduler:
    """Get the global scheduler instance"""
    global prediction_scheduler
    if prediction_scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")
    return prediction_scheduler


def shutdown_scheduler():
    """Shutdown the global scheduler"""
    global prediction_scheduler
    if prediction_scheduler is not None:
        prediction_scheduler.shutdown()
        prediction_scheduler = None
