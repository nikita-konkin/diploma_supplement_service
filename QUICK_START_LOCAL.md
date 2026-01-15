# Quick Start Guide - Running Services Locally Without Docker

This guide helps you quickly set up and run all services locally for development without Docker.

## 📋 Prerequisites

Before starting, ensure you have the following installed:

- **Python 3.8+** - [Download](https://www.python.org/downloads/)
- **Java 17+** - [Download](https://adoptium.net/)
- **Maven 3.6+** - [Download](https://maven.apache.org/download.cgi)
- **curl** - Usually pre-installed (Windows 10+ includes it)

## 🚀 Quick Start (All Services)

### Step 1: Start Python Pivot Engine (Port 8000)

Open a terminal/command prompt:

```bash
cd python-engine
pip install -r requirements.txt
python app.py
```

Keep this terminal open. You should see:
```
* Running on http://0.0.0.0:8000
```

### Step 2: Start Python XML Engine (Port 8001)

Open a **new** terminal/command prompt:

```bash
cd python-xml-engine
pip install -r requirements.txt
python app.py
```

Keep this terminal open. You should see:
```
* Running on http://0.0.0.0:8001
```

### Step 3: Start Java API Gateway (Port 8080)

Open a **third** terminal/command prompt:

**Windows:**
```batch
cd java-api
run-local.bat
```

**Linux/Mac:**
```bash
cd java-api
chmod +x run-local.sh
./run-local.sh
```

**PowerShell:**
```powershell
cd java-api
.\run-local.ps1
```

The script will:
- ✓ Check prerequisites
- ✓ Verify Python services are running
- ✓ Build the Java application
- ✓ Start the server

## 🌐 Access the Application

Once all services are running:

- **Main Web Interface**: http://localhost:8080/
- **Health Check**: http://localhost:8080/health

### Service Endpoints

| Service | Port | Health Check | Purpose |
|---------|------|--------------|---------|
| Java API Gateway | 8080 | http://localhost:8080/health | Main entry point & web UI |
| Python Pivot Engine | 8000 | http://localhost:8000/health | XLSX processing |
| Python XML Engine | 8001 | http://localhost:8001/health | Diploma XML generation |

## ✅ Verify Everything is Running

Open a terminal and run:

```bash
curl http://localhost:8080/health
curl http://localhost:8000/health
curl http://localhost:8001/health
```

All should return a JSON response with `"status": "healthy"` or similar.

## 🔧 Configuration

### Default Settings

All services run with default settings suitable for local development:

- **Java API**: Port 8080
- **Python Pivot Engine**: Port 8000
- **Python XML Engine**: Port 8001

### Custom Configuration

If you need to change ports or other settings:

1. **For Java API**, set environment variables before running:

   **Windows (CMD):**
   ```batch
   set API_PORT=8085
   set PIVOT_ENGINE_BASE_URL=http://localhost:8000
   set XML_API_BASE_URL=http://localhost:8001
   run-local.bat
   ```

   **Windows (PowerShell):**
   ```powershell
   $env:API_PORT="8085"
   $env:PIVOT_ENGINE_BASE_URL="http://localhost:8000"
   $env:XML_API_BASE_URL="http://localhost:8001"
   .\run-local.ps1
   ```

   **Linux/Mac:**
   ```bash
   export API_PORT=8085
   export PIVOT_ENGINE_BASE_URL=http://localhost:8000
   export XML_API_BASE_URL=http://localhost:8001
   ./run-local.sh
   ```

2. **For Python services**, edit their respective configuration files or environment variables.

## 🛑 Stopping Services

To stop any service:

1. Go to the terminal where it's running
2. Press `Ctrl+C`

## 📝 Testing the API

### Upload an XLSX File

```bash
curl -X POST -F "file=@path/to/your/file.xlsx" http://localhost:8080/pivot
```

### Check Health Status

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "XLSX Pivot Gateway",
  "timestamp": "2024-01-14T12:34:56Z"
}
```

## 🐛 Troubleshooting

### Port Already in Use

**Error**: `Address already in use` or `Port 8080 is already in use`

**Solution**: Change the port:
```bash
# Linux/Mac
export API_PORT=8085
./run-local.sh

# Windows
set API_PORT=8085
run-local.bat
```

### Java Not Found

**Error**: `java: command not found` or `'java' is not recognized`

**Solution**: 
1. Install Java 17+ from https://adoptium.net/
2. Ensure Java is in your PATH
3. Verify: `java -version`

### Maven Not Found

**Error**: `mvn: command not found` or `'mvn' is not recognized`

**Solution**:
1. Install Maven from https://maven.apache.org/download.cgi
2. Add Maven to your PATH
3. Verify: `mvn -version`

### Python Dependencies Error

**Error**: `ModuleNotFoundError` or missing dependencies

**Solution**:
```bash
cd python-engine  # or python-xml-engine
pip install --upgrade pip
pip install -r requirements.txt
```

### Connection Refused to Python Services

**Error**: Java API can't connect to Python services

**Solution**:
1. Verify Python services are running:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8001/health
   ```
2. Check firewall settings
3. Ensure services are bound to `0.0.0.0` not just `127.0.0.1`

### Build Failures

**Error**: Maven build fails

**Solution**:
```bash
cd java-api
mvn clean
mvn package -DskipTests
```

If still failing, delete Maven cache:
- Windows: `rmdir /s %USERPROFILE%\.m2\repository`
- Linux/Mac: `rm -rf ~/.m2/repository`

Then rebuild: `mvn package`

## 📚 Additional Resources

### Detailed Documentation

- **Java API**: See `java-api/README-LOCAL.md` for detailed configuration options
- **Main Project**: Check the root `README.md` for overall architecture
- **Docker Setup**: See `docker-compose.yml` for containerized deployment

### Environment Variables Reference

See `java-api/.env.example` for all available environment variables and their descriptions.

## 🔄 Development Workflow

### Making Changes

1. **Python Services**: Just save your changes and restart the service (Ctrl+C, then `python app.py`)
2. **Java API**: 
   - Save your changes
   - Stop the server (Ctrl+C)
   - Rebuild: `mvn package -DskipTests`
   - Restart: `./run-local.sh` (or `.bat` on Windows)

### Hot Reload (Optional)

For faster Java development, consider using a dev tool like JRebel or Spring DevTools, or run with Maven:

```bash
cd java-api
mvn clean compile exec:java
```

## 🎯 Next Steps

1. **Access the web interface**: http://localhost:8080/
2. **Upload a test XLSX file** to test the pivot functionality
3. **Generate diploma XML** using the XML generation endpoint
4. **Review the logs** in each terminal for debugging

## 💡 Tips

- **Keep all three terminals visible** so you can monitor logs
- **Use tmux or screen** on Linux/Mac to manage multiple sessions
- **Windows Terminal** with split panes works great on Windows
- **Check health endpoints** before testing to ensure all services are ready
- **Look at terminal logs** for detailed error messages

## 🆘 Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review the detailed README in `java-api/README-LOCAL.md`
3. Check service logs in each terminal
4. Verify all prerequisites are correctly installed
5. Ensure all ports (8000, 8001, 8080) are available

## 📊 Service Architecture

```
┌─────────────────────────────────────────┐
│  Browser / API Client                   │
│  http://localhost:8080                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Java API Gateway (Port 8080)           │
│  - Web Interface                        │
│  - Request Routing                      │
│  - File Handling                        │
└──────────┬──────────────┬───────────────┘
           │              │
           ▼              ▼
┌──────────────────┐  ┌──────────────────┐
│ Python Pivot     │  │ Python XML       │
│ Engine (8000)    │  │ Engine (8001)    │
│ - XLSX Process   │  │ - XML Generation │
└──────────────────┘  └──────────────────┘
```

## ✨ You're All Set!

Your local development environment is now ready. Happy coding! 🎉