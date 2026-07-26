# 🔌 Port Reference - Stock Analyzer

**Last Updated**: 2025-11-12
**Status**: ✅ Production-Ready (No more Windows Hyper-V conflicts!)

---

## 📋 Current Port Configuration

| Service | Host Port | Container Port | URL | Status |
|---------|-----------|----------------|-----|--------|
| **Frontend** (React) | `3000` | `3000` | http://localhost:3000 | ✅ Standard |
| **Backend** (FastAPI) | `8080` | `8080` | http://localhost:8080 | ✅ Standard |
| **API Docs** (Swagger) | `8080` | `8080` | http://localhost:8080/docs | ✅ Standard |
| **Database** (PostgreSQL) | `5432` | `5432` | `localhost:5432` | ✅ Standard |
| **Redis** (Cache/Queue) | `7379` | `6379` | `localhost:7379` | ✅ Safe Port |
| **Flower** (Celery Monitor) | `5555` | `5555` | http://localhost:5555 | ✅ Standard |

---

## 🎯 Quick Access

```bash
# Frontend (Dashboard)
open http://localhost:3000

# Backend API Documentation
open http://localhost:8080/docs

# Celery Task Monitoring
open http://localhost:5555
```

---

## 🔧 Port Selection Strategy

### Why These Ports?

1. **3000** (Frontend): React/Node.js standard
   - Used by 95% of React applications
   - Well-documented, easy to remember

2. **8080** (Backend): Python/FastAPI standard
   - Django/FastAPI convention
   - Most Python tutorials use this

3. **5432** (PostgreSQL): Database standard
   - Universal PostgreSQL port
   - All DB tools recognize it

4. **7379** (Redis): **Custom high port**
   - Standard Redis is 6379, but conflicts with Windows
   - 7xxx range is safe from Hyper-V conflicts
   - Easy to remember: 7379 ≈ 6379 + 1000

5. **5555** (Flower): Celery standard
   - Official Flower default port
   - Monitoring tools expect this

---

## ⚠️ Windows Hyper-V Conflicts (SOLVED)

### Previous Issues
- Port 6380 (Flower): Reserved by Windows (range 6374-6473)
- Port 6379 (Redis): Reserved by Windows (range 6374-6473)
- Port 5500 (Redis): Unpredictable conflicts

### Solution Applied
✅ Moved Redis to **7379** (high port, safe zone)
✅ Moved Flower to **5555** (standard, rarely conflicts)
✅ Frontend to **3000** (standard, below conflict range)

### Result
**Zero conflicts after Windows restart!** 🎉

---

## 🚀 For Production/Deployment

### Docker Swarm / Kubernetes
- Use service discovery (DNS names)
- Ports handled by orchestrator
- No manual port mapping needed

### Cloud Platforms
- **Heroku**: Uses dynamic $PORT variable
- **AWS ECS**: Managed container networking
- **Google Cloud Run**: Auto-assigned ports
- **Azure Container Apps**: Managed ports

### Traditional VPS (Linux)
- Use standard ports (3000, 8080, 5432, 6379, 5555)
- No Windows Hyper-V issues on Linux!
- Configure firewall: `ufw allow 3000,8080,5432`

---

## 🛠️ Changing Ports (If Needed)

### Edit docker-compose.yml
```yaml
services:
  frontend:
    ports:
      - "YOUR_PORT:3000"  # Change YOUR_PORT
```

### Then restart:
```bash
docker-compose down
docker-compose up -d
```

### Update .env (if using environment variables)
```bash
FRONTEND_PORT=3000
BACKEND_PORT=8080
DB_PORT=5432
REDIS_PORT=7379
FLOWER_PORT=5555
```

---

## 📊 Port Usage Check

### See what's using a port:
```powershell
# Windows
netstat -ano | findstr ":3000"

# Find process ID, then:
tasklist | findstr "PID_NUMBER"
```

### Kill process using port:
```powershell
# Windows (as Admin)
taskkill /PID PID_NUMBER /F
```

---

## 🔒 Security Notes

### Development (Current Setup)
- All ports exposed to localhost only
- Docker internal network isolated
- Safe for local development

### Production Checklist
- [ ] Use HTTPS (reverse proxy: nginx/Traefik)
- [ ] Hide database port (5432) - only internal
- [ ] Hide Redis port (7379) - only internal
- [ ] Expose only frontend (3000/80/443) + backend API (8080/443)
- [ ] Use environment variables for secrets
- [ ] Enable Docker secrets management
- [ ] Configure firewall rules

---

## 📝 Maintenance

### Check service health:
```bash
docker-compose ps
```

### View logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
```

### Restart services:
```bash
# Restart all
docker-compose restart

# Restart one
docker-compose restart backend
```

---

## ✅ Verification Checklist

After starting services, verify:

- [ ] Frontend loads: http://localhost:3000
- [ ] Backend health: http://localhost:8080/health
- [ ] API docs load: http://localhost:8080/docs
- [ ] Database connects: `psql -h localhost -p 5432 -U stockuser -d stock_analyzer`
- [ ] Redis responds: `redis-cli -p 7379 ping` (should return "PONG")
- [ ] Flower dashboard: http://localhost:5555

---

**Last tested**: 2025-11-12
**Windows conflicts**: ✅ RESOLVED
**All services**: ✅ RUNNING
