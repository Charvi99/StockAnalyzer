"""
Test Celery task timestamp updates

This script tests that analyze_stock_comprehensive properly updates analysis timestamps
"""
from app.db.database import SessionLocal
from app.models.stock import Stock
from app.services.analysis_completeness import AnalysisCompletenessService
from app.tasks.analysis_tasks import analyze_stock_comprehensive
import time

def test_celery_timestamp_updates():
    """Test that Celery task updates timestamps correctly"""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("TEST: Celery Task Timestamp Updates")
        print("=" * 80)

        # Get a test stock with price data
        print("\n[1] Finding a test stock with sufficient price data...")
        test_stock = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.symbol == 'AAPL'  # Use AAPL as it likely has data
        ).first()

        if not test_stock:
            print("   [WARNING] AAPL not found, using any tracked stock...")
            test_stock = db.query(Stock).filter(Stock.is_tracked == True).first()

        if not test_stock:
            print("   [ERROR] No tracked stocks found!")
            return

        print(f"   Using stock: {test_stock.symbol} (ID: {test_stock.id})")

        # Check BEFORE state
        print("\n[2] BEFORE analysis:")
        before_summary = AnalysisCompletenessService.get_completeness_summary(test_stock, db)
        print(f"   Analysis Score: {before_summary['analysis_score']:.2f}")
        print(f"   Analysis Complete: {before_summary['analysis_complete']}")
        print(f"   Missing: {', '.join(before_summary['missing_components'])}")

        # Run analysis synchronously (not as Celery task, just call the function)
        print(f"\n[3] Running comprehensive analysis for {test_stock.symbol}...")
        print("   This may take 30-60 seconds...")

        result = analyze_stock_comprehensive(test_stock.id, test_stock.symbol)

        print(f"\n[4] Analysis completed!")
        print(f"   Status: {result.get('overall_status')}")
        print(f"   Successful Steps: {result.get('successful_steps')}/{result.get('total_steps')}")
        print(f"   Analysis Score: {result.get('analysis_score', 0):.2f}")
        print(f"   Analysis Complete: {result.get('analysis_complete')}")

        # Refresh stock from database to get updated values
        db.refresh(test_stock)

        # Check AFTER state
        print("\n[5] AFTER analysis:")
        after_summary = AnalysisCompletenessService.get_completeness_summary(test_stock, db)
        print(f"   Analysis Score: {after_summary['analysis_score']:.2f}")
        print(f"   Analysis Complete: {after_summary['analysis_complete']}")
        print(f"   Missing: {', '.join(after_summary['missing_components']) if after_summary['missing_components'] else 'None'}")

        print("\n[6] Component timestamps:")
        for component, details in after_summary['components'].items():
            if details['last_analyzed']:
                print(f"   {component}: {details['last_analyzed']} ({details['age_hours']:.1f}h ago)")
            else:
                print(f"   {component}: Never analyzed")

        # Verify improvement
        print("\n[7] Verification:")
        if after_summary['analysis_score'] > before_summary['analysis_score']:
            print(f"   [SUCCESS] Score improved from {before_summary['analysis_score']:.2f} to {after_summary['analysis_score']:.2f}")
        else:
            print(f"   [WARNING] Score did not improve (was {before_summary['analysis_score']:.2f}, now {after_summary['analysis_score']:.2f})")

        if test_stock.last_comprehensive_analysis:
            print(f"   [SUCCESS] last_comprehensive_analysis timestamp was set: {test_stock.last_comprehensive_analysis}")
        else:
            print(f"   [ERROR] last_comprehensive_analysis was not set!")

        print("\n" + "=" * 80)
        print("[SUCCESS] Celery timestamp update test completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_celery_timestamp_updates()
