# 🚀 START HERE - Running Services Locally

Welcome! This guide helps you run the diploma supplement service locally without Docker.

## ⚡ Quick Start (5 Minutes)

### Prerequisites
- Java 17+ ([Download](https://adoptium.net/))
- Maven 3.6+ ([Download](https://maven.apache.org/download.cgi))
- Python 3.8+ ([Download](https://www.python.org/downloads/))

### One Command Setup

**Windows:**
```batch
start-all-local.bat
```

**Linux/Mac:**
```bash
chmod +x start-all-local.sh
./start-all-local.sh
```

This starts all 3 services in separate windows!

### Access the Application
Once started (wait ~30-60 seconds), open:
👉 **http://localhost:8080/**

## 📖 Documentation

Pick the guide that fits your needs:

### 1. **QUICK_START_LOCAL.md** ⭐ RECOMMENDED
Complete step-by-step guide for first-time setup.
- Prerequisites checklist
- Service startup instructions
- Verification steps
- Troubleshooting

### 2. **java-api/README-LOCAL.md**
Detailed documentation for Java API specifically.
- Configuration options
- Environment variables
- Advanced usage
- Development tips

### 3. **SETUP_SUMMARY.md**
Overview of all created files and scripts.
- What was created
- How everything works
- Quick reference

## 🎯 Quick Reference

### Service Ports
| Service | Port | Purpose |
|---------|------|---------|
| Java API Gateway | 8080 | Main application & UI |
| Python Pivot Engine | 8000 | XLSX processing |
| Python XML Engine | 8001 | XML generation |

### Health Checks
```bash
curl http://localhost:8080/health  # Java API
curl http://localhost:8000/health  # Python Pivot
curl http://localhost:8001/health  # Python XML
```

### Manual Start (Individual Services)

**Python Pivot Engine (Terminal 1):**
```bash
cd python-engine
pip install -r requirements.txt
python app.py
```

**Python XML Engine (Terminal 2):**
```bash
cd python-xml-engine
pip install -r requirements.txt
python app.py
```

**Java API (Terminal 3):**

Windows:
```batch
cd java-api
run-local.bat
```

Linux/Mac:
```bash
cd java-api
./run-local.sh
```

PowerShell:
```powershell
cd java-api
.\run-local.ps1
```

## 🐛 Common Issues

### "Port already in use"
Change the port before starting:
```bash
export API_PORT=8085    # Linux/Mac
set API_PORT=8085       # Windows CMD
$env:API_PORT="8085"    # Windows PowerShell
```

### "Java not found"
Install Java 17+ and ensure it's in your PATH:
```bash
java -version  # Should show 17 or higher
```

### "Maven not found"
Install Maven and add to PATH:
```bash
mvn -version
```

### Python services not running
Start them first (see Manual Start above), then start Java API.

## 📁 Project Structure

```
diploma_supplement_service/
│
├── START_HERE_LOCAL.md           ⭐ You are here!
├── QUICK_START_LOCAL.md          📘 Complete guide
├── SETUP_SUMMARY.md              📋 Setup overview
│
├── start-all-local.bat           🚀 Start all (Windows)
├── start-all-local.sh            🚀 Start all (Linux/Mac)
│
├── java-api/
│   ├── run-local.bat             ▶️ Java runner (Windows)
│   ├── run-local.sh              ▶️ Java runner (Linux/Mac)
│   ├── run-local.ps1             ▶️ Java runner (PowerShell)
│   ├── README-LOCAL.md           📖 Detailed Java docs
│   └── .env.example              ⚙️ Config example
│
├── python-engine/                🐍 Pivot service
└── python-xml-engine/            🐍 XML service
```

## 🎓 Next Steps

1. ✅ **Run the quick start command** (see top of this file)
2. ✅ **Wait for services to start** (~30-60 seconds)
3. ✅ **Open http://localhost:8080/** in your browser
4. ✅ **Upload a test XLSX file** to verify functionality
5. ✅ **Read QUICK_START_LOCAL.md** for more details

## 💡 Tips

- **Keep all 3 terminals visible** to monitor logs
- **Check health endpoints** before testing
- **Windows Terminal** with split panes works great
- **Use tmux/screen** on Linux/Mac for session management
- **Set environment variables** to customize configuration

## 🆘 Need Help?

1. Check **QUICK_START_LOCAL.md** - Troubleshooting section
2. Review **java-api/README-LOCAL.md** - Detailed options
3. Check service logs in each terminal window
4. Verify all prerequisites are installed
5. Ensure ports 8000, 8001, 8080 are available

## 🎉 Ready to Go!

Everything you need is set up. Just run the quick start command and you're ready to develop!

**Windows:** `start-all-local.bat`  
**Linux/Mac:** `./start-all-local.sh`

Happy coding! 🚀