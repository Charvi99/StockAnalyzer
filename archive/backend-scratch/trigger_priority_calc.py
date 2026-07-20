from app.db.database import SessionLocal
from app.services.priority_calculator import PriorityCalculator

db = SessionLocal()
try:
    calculator = PriorityCalculator(db)
    print("Starting priority recalculation...")
    result = calculator.recalculate_all_priorities()

    print(f"\nPriority Recalculation Complete:")
    print(f"  High priority: {result['high_priority']} stocks")
    print(f"  Medium priority: {result['medium_priority']} stocks")
    print(f"  Low priority: {result['low_priority']} stocks")
    print(f"  Errors: {result['errors']} stocks")
finally:
    db.close()
