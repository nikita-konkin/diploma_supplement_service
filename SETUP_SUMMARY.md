# Setup Summary - Local Development Environment

## 📦 What Was Created

A complete set of runner scripts and documentation to run the Java API service locally without Docker.

### Created Files

#### Main Runner Scripts (java-api/)
1. **`run-local.sh`** - Bash script for Linux/Mac
2. **`run-local.bat`** - Batch script for Windows Command Prompt
3. **`run-local.ps1`** - PowerShell script for Windows PowerShell
4. **`README-LOCAL.md`** - Comprehensive documentation for running locally
5. **`.env.example`** - Example environment configuration file

#### Convenience Scripts (Root Directory)
1. **`start-all-local.sh`** - Start all services at once (Linux/Mac)
2. **`start-all-local.bat`** - Start all services at once (Windows)
3. **`QUICK_START_LOCAL.md`** - Quick start guide for local development

## 🚀 How to Use

### Option 1: Quick Start (All Services at Once)

**Windows:**
```batch
start-all-local.bat
```

**Linux/Mac:**
```bash
chmod +x start-all-local.sh
./start-all-local.sh
```

This opens 3 separate terminal windows/tabs for each service.

### Option 2: Manual Start (Individual Services)

**Step 1: Start Python Pivot Engine (Port 8000)**
```bash
cd python-engine
pip install -r requirements.txt
python app.py
```

**Step 2: Start Python XML Engine (Port 8001)**
```bash
cd python-xml-engine
pip install -r requirements.txt
python app.py
```

**Step 3: Start Java API Gateway (Port 8080)**

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

## 🎯 What the Scripts Do

The Java API runner scripts automatically:

1. ✅ **Check Prerequisites**
   - Verify Java 17+ is installed
   - Verify Maven is installed
   - Check Java version compatibility

2. ✅ **Verify Dependencies**
   - Check if Python Pivot Engine is running (port 8000)
   - Check if Python XML Engine is running (port 8001)
   - Warn if services are not available

3. ✅ **Build Application**
   - Run `mvn clean package`
   - Create fat JAR with all dependencies
   - Skip tests for faster builds

4. ✅ **Configure Environment**
   - Set default environment variables
   - Allow customization via environment variables
   - Display current configuration

5. ✅ **Start Server**
   - Launch Java API on port 8080 (default)
   - Show startup messages
   - Display access URLs

## 🔧 Configuration

### Default Settings
```
API_PORT=8080
PIVOT_ENGINE_BASE_URL=http://localhost:8000
XML_API_BASE_URL=http://localhost:8001
PIVOT_API_PATH=/pivot
XML_GENERATE_PATH=/generate-xml
JAVA_OPTS=-Xmx512m -Xms256m
```

### Customizing Settings

**Windows (CMD):**
```batch
set API_PORT=8085
set PIVOT_ENGINE_BASE_URL=http://localhost:8000
run-local.bat
```

**Windows (PowerShell):**
```powershell
$env:API_PORT="8085"
$env:PIVOT_ENGINE_BASE_URL="http://localhost:8000"
.\run-local.ps1
```

**Linux/Mac:**
```bash
export API_PORT=8085
export PIVOT_ENGINE_BASE_URL=http://localhost:8000
./run-local.sh
```

## 📋 Prerequisites

Before running locally, ensure you have:

- **Java 17+** - [Download from Adoptium](https://adoptium.net/)
- **Maven 3.6+** - [Download from Apache](https://maven.apache.org/download.cgi)
- **Python 3.8+** - [Download from Python.org](https://www.python.org/downloads/)
- **curl** - Usually pre-installed (Windows 10+ includes it)

### Verify Prerequisites

```bash
java -version    # Should show version 17 or higher
mvn -version     # Should show Maven 3.6+
python --version # Should show Python 3.8+
curl --version   # Should show curl version
```

## 🌐 Access Points

Once all services are running:

| Service | URL | Description |
|---------|-----|-------------|
| Web Interface | http://localhost:8080/ | Main application UI |
| Health Check | http://localhost:8080/health | Java API health status |
| Pivot Engine Health | http://localhost:8000/health | Python pivot service |
| XML Engine Health | http://localhost:8001/health | Python XML service |

## 🧪 Testing the Setup

### 1. Check All Services
```bash
curl http://localhost:8080/health
curl http://localhost:8000/health
curl http://localhost:8001/health
```

### 2. Upload Test File
```bash
curl -X POST -F "file=@path/to/test.xlsx" http://localhost:8080/pivot
```

### 3. Check Web Interface
Open in browser: http://localhost:8080/

## 🐛 Common Issues & Solutions

### Issue: Port Already in Use
```
Error: Address already in use (port 8080)
```
**Solution:** Change the port
```bash
export API_PORT=8085  # Linux/Mac
set API_PORT=8085     # Windows
```

### Issue: Java Not Found
```
Error: java: command not found
```
**Solution:** Install Java 17+ and add to PATH

### Issue: Maven Not Found
```
Error: mvn: command not found
```
**Solution:** Install Maven and add to PATH

### Issue: Python Services Not Running
```
Warning: Python services are not running
```
**Solution:** Start Python services first (see Option 2 above)

### Issue: Build Failures
```
Error: Build failed
```
**Solution:** Clean and rebuild
```bash
cd java-api
mvn clean
mvn package -DskipTests
```

## 📚 Documentation Structure

```
diploma_supplement_service/
│
├── QUICK_START_LOCAL.md          # Quick start guide (read this first!)
├── SETUP_SUMMARY.md              # This file - overview of setup
│
├── start-all-local.sh            # Start all services (Linux/Mac)
├── start-all-local.bat           # Start all services (Windows)
│
└── java-api/
    ├── run-local.sh              # Java runner (Linux/Mac)
    ├── run-local.bat             # Java runner (Windows CMD)
    ├── run-local.ps1             # Java runner (Windows PowerShell)
    ├── README-LOCAL.md           # Detailed Java API documentation
    └── .env.example              # Example configuration
```

## 🎓 Next Steps

1. **Read Quick Start Guide**: See `QUICK_START_LOCAL.md` for step-by-step instructions
2. **Review Java API Docs**: See `java-api/README-LOCAL.md` for detailed options
3. **Configure Environment**: Copy and edit `java-api/.env.example` if needed
4. **Start Services**: Use the runner scripts to start services
5. **Test Application**: Access http://localhost:8080/ and upload a test file

## 💡 Development Tips

### Running Multiple Configurations

You can run multiple instances with different ports:

**Terminal 1 (Dev Environment):**
```bash
export API_PORT=8080
./run-local.sh
```

**Terminal 2 (Test Environment):**
```bash
export API_PORT=8081
export PIVOT_ENGINE_BASE_URL=http://test-server:8000
./run-local.sh
```

### Debug Mode

Enable debug logging:
```bash
java -Dorg.slf4j.simpleLogger.defaultLogLevel=debug -jar target/xlsx-pivot-gateway.jar
```

### Remote Debugging

Enable remote debugging:
```bash
java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005 -jar target/xlsx-pivot-gateway.jar
```

Connect your IDE debugger to `localhost:5005`

## 🔄 Comparison: Local vs Docker

| Aspect | Local Development | Docker |
|--------|------------------|--------|
| **Setup Time** | Faster (no image build) | Slower (build images) |
| **Resource Usage** | Lower | Higher |
| **Prerequisites** | Java, Maven, Python | Only Docker |
| **Debugging** | Easier (direct access) | Container access needed |
| **Hot Reload** | Faster | Slower |
| **Production Parity** | Lower | Higher |
| **Best For** | Development, Testing | Production, CI/CD |

## 🎉 You're Ready!

All scripts are ready to use. Choose your preferred method:

1. **Easiest**: Run `start-all-local.bat` (Windows) or `./start-all-local.sh` (Linux/Mac)
2. **Manual**: Start each service individually for more control
3. **Customized**: Set environment variables for custom configuration

For detailed instructions, see **QUICK_START_LOCAL.md**

Happy developing! 🚀