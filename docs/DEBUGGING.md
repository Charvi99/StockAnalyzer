# Debugging Guide for Stock Analyzer

This guide explains how to debug your Docker-based application using VSCode.

## Prerequisites

Install these VSCode extensions (VSCode will prompt you automatically if you open this project):
- **Dev Containers** - Work inside containers
- **Docker** - Manage containers
- **Python** - Python debugging
- **Debugpy** - Python remote debugging

## Method 1: Remote Debugging Python Backend (Recommended)

This lets you debug the Python backend running in Docker from your host VSCode.

### Setup

1. **Rebuild backend with debug support:**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.debug.yml up --build backend
   ```

2. **In VSCode:**
   - Open `backend/app/api/routes/stocks.py`
   - Set a breakpoint (click left of line number) in any function, e.g., line 10 in `get_stocks()`
   - Press `F5` or go to Run & Debug panel
   - Select "Python: Remote Attach (Docker Backend)"
   - Wait for "Debugger attached" message

3. **Trigger the breakpoint:**
   - Open browser to `http://localhost:8000/api/v1/stocks/`
   - VSCode will pause at your breakpoint
   - You can now:
     - Inspect variables (hover over them)
     - Step through code (F10 = step over, F11 = step into)
     - View call stack
     - Evaluate expressions in Debug Console

### How It Works

- `debugpy` runs inside the container on port 5678
- Port 5678 is exposed to your host machine
- VSCode connects to the debugger via `localhost:5678`
- Path mappings translate local paths to container paths

### Debugging Tips

**Set breakpoints before making requests:**
```python
# In backend/app/api/routes/stocks.py
@router.get("/", response_model=List[StockResponse])
def get_stocks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    stocks = db.query(Stock).offset(skip).limit(limit).all()  # <- Set breakpoint here
    return stocks
```

**Use Debug Console:**
- While paused at breakpoint, type in Debug Console:
  ```python
  stocks
  len(stocks)
  stocks[0].symbol
  db.execute("SELECT COUNT(*) FROM stocks").scalar()
  ```

**Conditional breakpoints:**
- Right-click on breakpoint red dot
- Select "Edit Breakpoint"
- Add condition: `stock_id == 1`

---

## Method 2: Attach VSCode to Running Container

Work entirely inside the container with full debugging capabilities.

### Setup

1. **Make sure containers are running:**
   ```bash
   docker-compose up -d
   ```

2. **Attach VSCode to container:**
   - Click green button in bottom-left corner of VSCode
   - Select "Dev Containers: Attach to Running Container..."
   - Choose `stock_analyzer_backend`
   - New VSCode window opens

3. **Install Python extension inside container:**
   - VSCode will prompt to install recommended extensions
   - Click "Install" for Python extension

4. **Open folder:**
   - File > Open Folder > `/app`

5. **Debug normally:**
   - Set breakpoints
   - Press F5
   - Select "Python Debugger: FastAPI"

### Advantages

- Full IntelliSense with container's Python packages
- Terminal runs inside container
- See exact environment that code runs in
- Can edit files (changes reflect on host due to volume mount)

---

## Method 3: Local Development (No Docker)

Run backend locally on your Windows machine for fastest debugging.

### Setup

1. **Install Python 3.11 on Windows**

2. **Create virtual environment:**
   ```bash
   cd backend
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Start only database in Docker:**
   ```bash
   docker-compose up database
   ```

4. **Debug in VSCode:**
   - Select "Python: FastAPI (Local - No Docker)" from debug dropdown
   - Press F5
   - Set breakpoints normally
   - Full debugging with fastest performance

### When to Use

- Rapid iteration during development
- Complex debugging scenarios
- Need to test with different Python versions
- Docker overhead slows you down

---

## Debugging React Frontend

### Browser DevTools (Primary Method)

1. **Start frontend:**
   ```bash
   docker-compose up frontend
   ```

2. **Open browser:**
   - Navigate to `http://localhost:3000`
   - Press `F12` to open DevTools
   - Go to "Sources" tab
   - Find your files under `localhost:3000/static/js`
   - Set breakpoints in browser

### VSCode Chrome Debugging

1. **Install "Debugger for Chrome" extension**

2. **Start frontend:**
   ```bash
   docker-compose up frontend
   ```

3. **In VSCode:**
   - Press F5
   - Select "Chrome: Debug Frontend"
   - Chrome opens and connects to VSCode
   - Set breakpoints in `.jsx` files in VSCode
   - Breakpoints work in both browser and VSCode

### React DevTools

1. **Install browser extension:**
   - Chrome: "React Developer Tools"
   - Firefox: "React DevTools"

2. **Use it:**
   - Open DevTools (`F12`)
   - New tabs: "Components" and "Profiler"
   - Inspect component state, props, hooks
   - Extremely useful for React-specific debugging

---

## Debugging Database Queries

### Method 1: pgAdmin (GUI)

```bash
# Add to docker-compose.yml temporarily:
pgadmin:
  image: dpage/pgadmin4
  environment:
    PGADMIN_DEFAULT_EMAIL: admin@admin.com
    PGADMIN_DEFAULT_PASSWORD: admin
  ports:
    - "5050:80"
```

Then access at `http://localhost:5050`

### Method 2: Command Line (psql)

```bash
# Connect to database container
docker-compose exec database psql -U stockuser -d stock_analyzer

# Run queries
SELECT * FROM stocks;
SELECT COUNT(*) FROM stock_prices;
\dt  -- List tables
\d stocks  -- Describe table
```

### Method 3: VSCode SQLTools Extension

1. Install "SQLTools" and "SQLTools PostgreSQL Driver"
2. Click SQLTools icon in sidebar
3. Add new connection:
   - **Host:** localhost
   - **Port:** 5432
   - **Database:** stock_analyzer
   - **Username:** stockuser
   - **Password:** stockpass123
4. Run queries directly from VSCode

---

## Viewing Logs

### Docker Compose Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend

# Since timestamp
docker-compose logs --since 2025-10-14T10:00:00 backend
```

### VSCode Docker Extension

1. Open Docker extension (sidebar)
2. Right-click on container
3. Select "View Logs"
4. Logs appear in VSCode terminal

---

## Common Debugging Scenarios

### "I changed Python code but nothing happens"

**Problem:** Auto-reload not working

**Solution:**
```bash
# Check if --reload is in the command
docker-compose logs backend | grep reload

# Restart backend
docker-compose restart backend

# If still not working, check volume mount:
docker-compose exec backend ls -la /app
```

### "Breakpoint never hits"

**Problem:** Debugger not attached or code path not executed

**Solutions:**
1. Verify debugger is attached (should see "Debugger attached" in terminal)
2. Check if your code path is actually executed (add `print()` statement)
3. Restart debug session
4. Rebuild container: `docker-compose up --build backend`

### "Module not found error"

**Problem:** Package installed locally but not in container

**Solution:**
```bash
# Add to requirements.txt
echo "your-package==1.0.0" >> backend/requirements.txt

# Rebuild
docker-compose up --build backend
```

### "Database connection refused"

**Problem:** Backend starting before database is ready

**Solution:**
- Check healthcheck in docker-compose.yml
- View database logs: `docker-compose logs database`
- Wait for "database system is ready to accept connections"

### "Port already in use"

**Problem:** Another process using the port

**Solutions:**
```bash
# Windows: Find process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /PID <PID> /F

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 instead
```

---

## Best Practices

1. **Use logging instead of print:**
   ```python
   import logging
   logger = logging.getLogger(__name__)

   logger.info("Fetching stocks")
   logger.debug(f"Query params: skip={skip}, limit={limit}")
   logger.error(f"Error occurred: {str(e)}")
   ```

2. **Add debug endpoints:**
   ```python
   @router.get("/debug/database")
   def debug_database(db: Session = Depends(get_db)):
       return {
           "table_count": db.execute("SELECT COUNT(*) FROM stocks").scalar(),
           "first_stock": db.query(Stock).first()
       }
   ```

3. **Use breakpoints strategically:**
   - Don't set too many at once
   - Place them at decision points
   - Use conditional breakpoints for loops

4. **Keep containers running:**
   - Use `docker-compose up -d` (detached mode)
   - Containers stay up while you work
   - Restart individual services: `docker-compose restart backend`

5. **Hot reload configuration:**
   - Backend: Auto-reloads on `.py` file changes (Uvicorn)
   - Frontend: Auto-reloads on `.js`/`.jsx` changes (React dev server)
   - Database schema: Requires restart or migration

---

## Quick Start Commands

```bash
# Start in debug mode
docker-compose -f docker-compose.yml -f docker-compose.debug.yml up

# Start in background
docker-compose up -d

# Rebuild single service
docker-compose up --build backend

# View logs
docker-compose logs -f backend

# Restart service
docker-compose restart backend

# Stop all
docker-compose down

# Fresh start (removes volumes)
docker-compose down -v && docker-compose up --build
```

---

## Troubleshooting Debug Connection

If remote debugging isn't working:

1. **Check debugpy is running:**
   ```bash
   docker-compose logs backend | grep debugpy
   # Should see: "Debugger listening on 0.0.0.0:5678"
   ```

2. **Verify port is exposed:**
   ```bash
   docker-compose ps
   # Should see: 0.0.0.0:5678->5678/tcp
   ```

3. **Test connection:**
   ```bash
   # Windows PowerShell
   Test-NetConnection -ComputerName localhost -Port 5678
   ```

4. **Check path mappings in launch.json:**
   ```json
   "pathMappings": [
     {
       "localRoot": "${workspaceFolder}/backend",
       "remoteRoot": "/app"
     }
   ]
   ```

5. **Restart everything:**
   ```bash
   docker-compose down
   docker-compose -f docker-compose.yml -f docker-compose.debug.yml up --build
   ```

---

## Resources

- [VSCode Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [VSCode Remote Development](https://code.visualstudio.com/docs/remote/containers)
- [debugpy Documentation](https://github.com/microsoft/debugpy)
- [FastAPI Debugging](https://fastapi.tiangolo.com/tutorial/debugging/)
- [React DevTools](https://react.dev/learn/react-developer-tools)
