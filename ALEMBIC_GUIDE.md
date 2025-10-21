# Alembic Database Migration Guide

This guide explains how to use Alembic for database migrations in the Stock Analyzer project.

## Overview

**Alembic** is a database migration tool for SQLAlchemy. It allows you to:
- Version control your database schema
- Track all schema changes over time
- Apply or rollback migrations easily
- Share schema changes with your team via code

## Why We Use Alembic

### Before Alembic
- Manual SQL scripts (`database/init.sql`)
- Hard to track what changed when
- Risk of schema drift between dev/prod
- Manual coordination for schema updates

### With Alembic
- ✅ Automatic migration generation from model changes
- ✅ Version history of all database changes
- ✅ Easy rollbacks if something goes wrong
- ✅ Migrations run automatically on container startup
- ✅ Team collaboration through code

## How It Works

### Automatic Migration on Startup

When you start the Docker containers with `docker-compose up`, the backend service:
1. Waits for the database to be ready
2. **Runs `alembic upgrade head`** to apply all pending migrations
3. Starts the FastAPI application

This is handled by the `backend/start.sh` script.

### Migration Files

Migrations are stored in `backend/alembic/versions/`:
- `c45f1698d64d_initial_migration.py` - Initial schema (all 8 tables)
- Future migrations will be added here

Each migration has:
- **Unique revision ID** (e.g., `c45f1698d64d`)
- **upgrade()** function - applies the changes
- **downgrade()** function - reverts the changes
- **Timestamp** of creation
- **Description** of what changed

## Common Workflows

### 1. Making Schema Changes

When you need to modify the database schema:

#### Step 1: Update the SQLAlchemy model

Edit `backend/app/models/stock.py`:

```python
class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False)
    name = Column(String(255))

    # NEW FIELD
    description = Column(Text, nullable=True)  # Add this line
```

#### Step 2: Generate the migration

**Option A: Using Docker (recommended)**
```bash
docker-compose exec backend ./migrate.sh create "add stock description field"
```

**Option B: Locally (if you have the environment set up)**
```bash
cd backend
python migrate.py create "add stock description field"
# or
./migrate.sh create "add stock description field"
```

This will create a new migration file like:
```
backend/alembic/versions/abc123def456_add_stock_description_field.py
```

#### Step 3: Review the generated migration

Open the file and verify it looks correct:
```python
def upgrade() -> None:
    op.add_column('stocks', sa.Column('description', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('stocks', 'description')
```

#### Step 4: Apply the migration

The migration will be applied automatically when you restart the backend:
```bash
docker-compose restart backend
```

Or apply it immediately:
```bash
docker-compose exec backend ./migrate.sh upgrade
```

### 2. Viewing Migration Status

Check which migrations have been applied:
```bash
docker-compose exec backend ./migrate.sh current
```

View all migrations:
```bash
docker-compose exec backend ./migrate.sh history
```

Check if there are pending migrations:
```bash
docker-compose exec backend ./migrate.sh check
```

### 3. Rolling Back Migrations

If you need to undo the last migration:
```bash
docker-compose exec backend ./migrate.sh downgrade
```

Rollback multiple migrations:
```bash
docker-compose exec backend ./migrate.sh downgrade -2  # Rollback 2 migrations
```

Rollback to a specific revision:
```bash
docker-compose exec backend alembic downgrade abc123def456
```

### 4. Fresh Database Setup

To start with a clean database:

```bash
# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v

# Start fresh - migrations will run automatically
docker-compose up --build
```

## Migration Helper Scripts

We provide two helper scripts:

### migrate.sh (Bash)
```bash
./migrate.sh create "message"    # Create new migration
./migrate.sh upgrade             # Apply all migrations
./migrate.sh downgrade           # Rollback one migration
./migrate.sh current             # Show current revision
./migrate.sh history             # Show migration history
./migrate.sh check               # Check for pending migrations
```

### migrate.py (Python)
Same commands as above, works on Windows without Bash:
```bash
python migrate.py create "message"
python migrate.py upgrade
# etc.
```

## Common Migration Scenarios

### Adding a New Column

**Model change:**
```python
class Stock(Base):
    # ... existing fields ...
    market_cap = Column(BigInteger, nullable=True)
```

**Migration command:**
```bash
docker-compose exec backend ./migrate.sh create "add market_cap to stocks"
```

### Adding a New Table

**Model change:**
```python
class WatchList(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    user_id = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
```

**Migration command:**
```bash
docker-compose exec backend ./migrate.sh create "add watchlists table"
```

### Adding an Index

**Model change:**
```python
class StockPrice(Base):
    # ... existing fields ...

    __table_args__ = (
        Index('idx_stock_prices_close', 'close'),
    )
```

**Migration command:**
```bash
docker-compose exec backend ./migrate.sh create "add index on stock_prices close"
```

### Renaming a Column

**Not automatically detected!** You need to manually edit the migration:

```python
def upgrade() -> None:
    op.alter_column('stocks', 'sector', new_column_name='industry_sector')

def downgrade() -> None:
    op.alter_column('stocks', 'industry_sector', new_column_name='sector')
```

## Best Practices

### 1. Always Review Generated Migrations
Auto-generated migrations might not be perfect. Always review them before applying.

### 2. Test Migrations Locally First
```bash
# Apply migration
docker-compose exec backend ./migrate.sh upgrade

# Test your application
# If something's wrong, rollback
docker-compose exec backend ./migrate.sh downgrade
```

### 3. One Migration Per Logical Change
Don't bundle unrelated changes in one migration. Create separate migrations for:
- Adding a table
- Adding an index
- Modifying a column

### 4. Write Descriptive Messages
```bash
# Good
./migrate.sh create "add user_email column to stocks table"

# Bad
./migrate.sh create "update"
```

### 5. Never Edit Applied Migrations
Once a migration has been applied (especially in production), never edit it. Create a new migration instead.

### 6. Keep Migrations Backward Compatible When Possible
If adding a new column, make it nullable initially:
```python
# Good - won't break existing code
new_field = Column(String(100), nullable=True)

# Risky - might break if existing code expects this field
new_field = Column(String(100), nullable=False)
```

## Troubleshooting

### "Database is not up to date" error

This means there are pending migrations:
```bash
docker-compose exec backend ./migrate.sh check
docker-compose exec backend ./migrate.sh upgrade
```

### Migration conflicts

If two people create migrations at the same time:
```bash
# Alembic will detect this and show an error
# Merge the migrations using:
alembic merge -m "merge migrations" revision1 revision2
```

### Can't connect to database during migration

Make sure the database is running:
```bash
docker-compose up database
# Wait for it to be healthy, then:
docker-compose up backend
```

### Wrong migration was applied

Rollback and fix:
```bash
# Rollback the bad migration
docker-compose exec backend ./migrate.sh downgrade

# Fix the migration file or create a new one
./migrate.sh create "fix previous migration"

# Apply again
docker-compose exec backend ./migrate.sh upgrade
```

## Project Structure

```
backend/
├── alembic/                    # Alembic configuration
│   ├── versions/               # Migration files
│   │   └── c45f1698d64d_initial_migration.py
│   ├── env.py                  # Alembic environment config
│   ├── script.py.mako          # Template for new migrations
│   └── README
├── alembic.ini                 # Alembic settings
├── migrate.sh                  # Bash helper script
├── migrate.py                  # Python helper script
├── start.sh                    # Startup script (runs migrations)
└── app/
    ├── models/
    │   └── stock.py            # SQLAlchemy models
    └── db/
        └── database.py         # Database connection
```

## Advanced Topics

### Manual Migrations

If auto-generate doesn't work for complex changes:

```bash
# Create empty migration
docker-compose exec backend alembic revision -m "custom migration"

# Edit the file manually
# Add your SQL or SQLAlchemy operations
```

### Data Migrations

To migrate data (not just schema):

```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Schema change
    op.add_column('stocks', sa.Column('sector_id', sa.Integer()))

    # Data migration
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE stocks SET sector_id = 1 WHERE sector = 'Technology'")
    )

def downgrade():
    op.drop_column('stocks', 'sector_id')
```

### Offline Mode (SQL Generation)

Generate SQL without applying it:
```bash
alembic upgrade head --sql > migration.sql
```

## FAQs

**Q: Do migrations run automatically?**
A: Yes, when the backend container starts, it runs `alembic upgrade head` automatically via the `start.sh` script.

**Q: What happened to `init.sql`?**
A: It's still there for reference, but it's no longer used. We now use Alembic migrations instead.

**Q: Can I use raw SQL in migrations?**
A: Yes! Use `op.execute("your SQL here")` in the migration file.

**Q: How do I reset the database completely?**
A: `docker-compose down -v && docker-compose up --build` - this deletes the volume and starts fresh.

**Q: Can I see what SQL will be executed?**
A: Yes, use `alembic upgrade head --sql` to see the SQL without applying it.

**Q: What if I want to skip a migration?**
A: You can manually update the `alembic_version` table, but this is risky. Better to rollback properly or create a new migration to fix issues.

## Next Steps

Now that Alembic is set up, you can:

1. **Add database indexes** for performance optimization
   - Example: Index on `stock_prices.close` for faster queries

2. **Add new tables** for features like:
   - User accounts
   - Watchlists
   - Alerts
   - Portfolio tracking

3. **Modify existing tables** safely:
   - Add columns for new features
   - Add constraints
   - Create composite indexes

All changes will be version-controlled and easily deployable!

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
