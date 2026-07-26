# Automatic Fetching - Quick Start Guide

**Status**: Week 1 Infrastructure Setup - READY TO TEST ✅
**Date**: 2025-10-30

---

## 🎉 What's Been Implemented

### ✅ Completed Files

1. **docker-compose.yml** - Added 4 new services:
   - `redis` - Message broker (port 6379)
   - `celery_worker` - Background task executor (7 workers)
   - `celery_beat` - Task scheduler (runs tasks on schedule)
   - `flower` - Monitoring dashboard (http://localhost:5555)

2. **backend/requirements.txt** - Added dependencies:
   - `celery==5.3.4` - Task queue library
   - `redis==5.0.1` - Redis Python client
   - `flower==2.0.1` - Celery monitoring

3. **backend/app/celery_app.py** - Celery configuration:
   - 15+ scheduled tasks (hourly, daily, weekly)
   - Priority queues (fetcher, processor, maintenance)
   - Rate limiting (5 requests/minute)
   - Logging and monitoring signals

4. **backend/app/tasks/** - Task modules:
   - `fetcher_tasks.py` - Data fetching tasks (placeholder implementations)
   - `processor_tasks.py` - Pattern detection tasks (placeholders)
   - `maintenance_tasks.py` - Cleanup tasks (placeholders)

---

## 🚀 How to Test the Setup

### Step 1: Rebuild Docker Containers

Since we added new dependencies to requirements.txt, rebuild:

```bash
docker-compose down
docker-compose build
docker-compose up
```

**What to expect:**
- You'll see 7 containers start: database, backend, frontend, redis, celery_worker, celery_beat, flower
- Celery worker should show: `[✓] celery@... ready`
- No errors about missing modules

### Step 2: Verify Services Are Running

Open these URLs in your browser:

1. **Frontend**: http://localhost:3000 (should work as before)
2. **Backend API**: http://localhost:8080/docs (should work as before)
3. **Flower Dashboard**: http://localhost:5555 ← **NEW!**

**Flower Dashboard should show:**
- ✅ Active workers: 1
- ✅ Queues: fetcher, processor, maintenance
- ✅ Tasks: 0 (no tasks run yet)

### Step 3: Test Celery with Debug Task

Open a new terminal and run:

```bash
docker-compose exec backend python -c "from app.celery_app import debug_task; result = debug_task.delay(); print('Task ID:', result.id)"
```

**What to expect:**
- Prints a task ID like: `Task ID: abc-123-def-456`
- Check Flower dashboard: You should see 1 completed task
- Check worker logs: `docker-compose logs celery_worker --tail=20`
  - Should show: `[TASK START] debug_task`
  - Should show: `[TASK SUCCESS] debug_task`

### Step 4: Test Database Connection

```bash
docker-compose exec backend python -c "from app.tasks.fetcher_tasks import test_fetch_task; result = test_fetch_task.delay(); print(result.get())"
```

**What to expect:**
```json
{
  "status": "success",
  "message": "Celery worker is running!",
  "stock_count": 335,
  "timestamp": "2025-10-30T12:00:00"
}
```

---

## 📊 What's Working vs What's Not

### ✅ Working Now

- Docker infrastructure (Redis, Celery, Flower)
- Celery worker can execute tasks
- Celery Beat scheduler is running
- Task queues are configured
- Rate limiting is configured
- Monitoring dashboard (Flower) is accessible

### ⏳ Not Yet Implemented (Week 2-4)

- **Actual data fetching** (placeholder tasks only)
- **Priority system** (no stock priorities yet)
- **Database tables** (need Alembic migration)
- **Incremental updates** (no tracking yet)
- **New Polygon endpoints** (dividends, splits, etc.)

**Tasks are scheduled but will log "Not yet implemented" when they run.**

---

## 🔍 Troubleshooting

### Problem: `celery_worker` container exits immediately

**Solution**: Check logs for missing dependencies
```bash
docker-compose logs celery_worker --tail=50
```

If you see `ModuleNotFoundError: No module named 'celery'`:
```bash
docker-compose build backend
docker-compose up celery_worker
```

### Problem: `redis` not accessible

**Solution**: Check Redis is healthy
```bash
docker-compose ps
# redis should show "healthy" status

docker-compose exec redis redis-cli ping
# Should return: PONG
```

### Problem: Flower shows "Connection Error"

**Solution**: Restart Flower container
```bash
docker-compose restart flower
```

### Problem: Tasks not executing

**Solution**: Check Celery Beat is running
```bash
docker-compose logs celery_beat --tail=20
# Should show scheduler sending tasks
```

---

## 📝 Next Steps (Week 2-4)

### Week 2: Core Fetching Tasks
1. Create Alembic migration for new tables (priorities, tracking)
2. Implement `fetch_stock_prices` task (incremental updates)
3. Implement priority calculator service
4. Test with 10 stocks

### Week 3: Additional Data Types
1. Implement dividend fetching (new Polygon endpoint)
2. Implement split fetching (new Polygon endpoint)
3. Implement short interest fetching (new Polygon endpoint)
4. Implement news fetching
5. Test with 50 stocks

### Week 4: Full Production
1. Implement pattern detection tasks
2. Scale to all 500 stocks
3. Monitor performance (Flower dashboard)
4. Add error alerting

---

## 🎯 Expected Scheduled Tasks (After Full Implementation)

Once everything is implemented, these tasks will run automatically:

### Hourly (Market Hours 9 AM - 4 PM ET)
- Fetch high-priority stocks (100 stocks)
- Check market status

### Every 2 Hours
- Fetch high-priority news

### Every 4 Hours
- Fetch medium-priority stocks (200 stocks)

### Daily
- 2 AM: Cleanup old task logs
- 3 AM: Recalculate stock priorities
- 5 PM: Fetch low-priority stocks (200 stocks)
- 6 PM: Detect patterns (all updated stocks)

### Weekly
- Sunday: Fetch dividends
- Monday: Fetch stock splits
- Tuesday: Fetch short interest data

---

## 🔗 Useful Commands

```bash
# View Celery worker logs (live)
docker-compose logs celery_worker -f

# View Celery Beat scheduler logs
docker-compose logs celery_beat --tail=50

# View Redis connection logs
docker-compose logs redis --tail=20

# Restart all Celery services
docker-compose restart celery_worker celery_beat flower

# Check task queue depth (Redis CLI)
docker-compose exec redis redis-cli llen celery

# Purge all pending tasks (CAREFUL!)
docker-compose exec celery_worker celery -A app.celery_app purge
```

---

## 📚 Documentation

- **Full Architecture**: `docs/AUTOMATIC_FETCHING_ARCHITECTURE.md`
- **Implementation Plan**: See Week 2-4 tasks in architecture doc
- **Roadmap**: `docs/ROADMAP.md` (see "Automatic Fetching Architecture")

---

**Status**: Infrastructure setup complete ✅
**Next**: Create Alembic migration for database tables

**Questions?** Check `docs/AUTOMATIC_FETCHING_ARCHITECTURE.md` for detailed explanations.
