"""
Test script for Phase 1: Analysis Completeness Tracking

This script tests:
1. AnalysisCompletenessService methods
2. Database schema changes
3. Analysis score calculation
"""
import sys
from app.db.database import SessionLocal
from app.models.stock import Stock
from app.services.analysis_completeness import AnalysisCompletenessService

def test_analysis_completeness():
    """Test the AnalysisCompletenessService"""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("PHASE 1 TEST: Analysis Completeness Tracking")
        print("=" * 80)

        # Test 1: Get all tracked stocks
        print("\n[Test 1] Loading tracked stocks...")
        stocks = db.query(Stock).filter(Stock.is_tracked == True).limit(5).all()
        print(f"   Loaded {len(stocks)} stocks for testing")

        if not stocks:
            print("   [ERROR] No tracked stocks found!")
            return

        # Test 2: Check completeness for each stock
        print("\n[Test 2] Checking analysis completeness...")
        for stock in stocks:
            summary = AnalysisCompletenessService.get_completeness_summary(stock, db)
            print(f"\n   Stock: {stock.symbol} (ID: {stock.id})")
            print(f"   - Analysis Score: {summary['analysis_score']:.2f}")
            print(f"   - Analysis Complete: {summary['analysis_complete']}")
            print(f"   - Missing Components: {', '.join(summary['missing_components']) if summary['missing_components'] else 'None'}")

            # Show component details
            for component, details in summary['components'].items():
                status = "[FRESH]" if not details['is_stale'] else "[STALE]" if details['last_analyzed'] else "[MISSING]"
                age_str = f"({details['age_hours']:.1f}h ago)" if details['age_hours'] else "(never)"
                print(f"      {component}: {status} {age_str}")

        # Test 3: Get stocks needing analysis
        print("\n[Test 3] Finding stocks needing analysis...")
        stocks_needing = AnalysisCompletenessService.get_stocks_needing_analysis(
            db=db,
            min_score_threshold=0.80,
            tracked_only=True,
            limit=10
        )
        print(f"   Found {len(stocks_needing)} stocks needing analysis (score < 0.80)")
        for stock in stocks_needing[:5]:  # Show first 5
            print(f"   - {stock.symbol}: score={stock.analysis_score:.2f}, priority={stock.priority}")

        # Test 4: Test should_trigger_analysis
        print("\n[Test 4] Testing analysis trigger logic...")
        test_stock = stocks[0]
        should_trigger = AnalysisCompletenessService.should_trigger_analysis(test_stock, db)
        print(f"   Stock: {test_stock.symbol}")
        print(f"   Should trigger analysis: {should_trigger}")

        # Test 5: Test missing components
        print("\n[Test 5] Testing missing components detection...")
        missing = AnalysisCompletenessService.get_missing_components(test_stock, db)
        print(f"   Stock: {test_stock.symbol}")
        print(f"   Missing components: {', '.join(missing) if missing else 'None'}")

        # Test 6: Database query performance
        print("\n[Test 6] Testing query performance with new indexes...")
        import time

        start = time.time()
        incomplete_stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.analysis_complete == False
        ).count()
        elapsed = time.time() - start
        print(f"   Found {incomplete_stocks} incomplete stocks in {elapsed*1000:.2f}ms")

        start = time.time()
        low_score_stocks = db.query(Stock).filter(
            Stock.is_tracked == True,
            Stock.analysis_score < 0.80
        ).count()
        elapsed = time.time() - start
        print(f"   Found {low_score_stocks} low-score stocks in {elapsed*1000:.2f}ms")

        print("\n" + "=" * 80)
        print("[SUCCESS] Phase 1 tests completed successfully!")
        print("=" * 80)
        print("\nNext Steps:")
        print("1. Run `analyze_stock_comprehensive` for a test stock")
        print("2. Verify timestamps are updated correctly")
        print("3. Verify analysis_score is calculated correctly")
        print("4. Move to Phase 2: Completeness Check API")

    except Exception as e:
        print(f"\n[ERROR] Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_analysis_completeness()
