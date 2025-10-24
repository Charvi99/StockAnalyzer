# Database Backups

This folder contains database backups for the Stock Analyzer application.

## Backup Files

- **`stock_analyzer_backup_YYYY-MM-DD.dump`** - Binary format (compressed, faster restore)
- **`stock_analyzer_backup_YYYY-MM-DD.sql`** - SQL format (human-readable, easier to edit)

## Creating a Backup

To create a new backup manually:

```bash
# Binary format (recommended)
docker exec stock_analyzer_db pg_dump -U stockuser -d stock_analyzer -F c > backups/stock_analyzer_backup_$(date +%Y-%m-%d).dump

# SQL format (human-readable)
docker exec stock_analyzer_db pg_dump -U stockuser -d stock_analyzer --clean --if-exists > backups/stock_analyzer_backup_$(date +%Y-%m-%d).sql
```

## Restoring from Backup

### Option 1: Restore Binary Format (.dump)

```bash
# Stop the backend first
docker-compose stop backend

# Drop and recreate the database
docker exec stock_analyzer_db psql -U stockuser -d postgres -c "DROP DATABASE IF EXISTS stock_analyzer;"
docker exec stock_analyzer_db psql -U stockuser -d postgres -c "CREATE DATABASE stock_analyzer;"

# Restore from binary backup
cat backups/stock_analyzer_backup_2025-10-22.dump | docker exec -i stock_analyzer_db pg_restore -U stockuser -d stock_analyzer -F c --clean --if-exists

# Restart services
docker-compose up -d backend
```

### Option 2: Restore SQL Format (.sql)

```bash
# Stop the backend first
docker-compose stop backend

# Restore from SQL backup (will drop and recreate tables)
cat backups/stock_analyzer_backup_2025-10-22.sql | docker exec -i stock_analyzer_db psql -U stockuser -d stock_analyzer

# Restart services
docker-compose up -d backend
```

## Notes

- The warnings about "circular foreign-key constraints" are normal for TimescaleDB and can be ignored
- The notice about "hypertable data are in the chunks" is expected for time-series tables
- Always stop the backend service before restoring to avoid connection conflicts
- Binary format (.dump) is recommended for production use (faster, compressed)
- SQL format (.sql) is better for inspection and manual editing

## Automated Backups

To create regular automated backups, you can:

1. **Windows Task Scheduler**: Create a scheduled task to run the backup command daily
2. **Cron Job (WSL/Linux)**: Add to crontab: `0 2 * * * cd /path/to/StockAnalyzer && docker exec stock_analyzer_db pg_dump -U stockuser -d stock_analyzer -F c > backups/backup_$(date +\%Y-\%m-\%d).dump`

## What's Backed Up

The backup includes:
- All stock price data
- All detected patterns
- Pattern detection metrics
- Watchlist and alerts
- User settings and preferences
- Database schema and indexes
- TimescaleDB hypertables and chunks

---

**Last Updated**: 2025-10-22
