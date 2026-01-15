# Running Java API Locally (Without Docker)

This guide explains how to run the Java API service locally without Docker for development purposes.

## Prerequisites

Before running the Java API locally, ensure you have the following installed:

1. **Java Development Kit (JDK) 17 or higher**
   - Download from: https://adoptium.net/ or https://www.oracle.com/java/technologies/downloads/
   - Verify installation: `java -version`

2. **Apache Maven 3.6 or higher**
   - Download from: https://maven.apache.org/download.cgi
   - Verify installation: `mvn -version`

3. **curl** (for health checks)
   - Windows: Included in Windows 10+ or install from https://curl.se/windows/
   - Linux/Mac: Usually pre-installed
   - Verify installation: `curl --version`

## Quick Start

### On Windows:

```batch
cd java-api
run-local.bat
```

### On Linux/Mac:

```bash
cd java-api
chmod +x run-local.sh
./run-local.sh
```

The script will:
1. Check if Java and Maven are properly installed
2. Check if Python services are running
3. Build the application using Maven
4. Start the Java API server on port 8080 (default)

## Configuration

The runner scripts use environment variables for configuration. You can customize them before running:

### Environment Variables

| Variable | Default Value | Description |
|----------|--------------|-------------|
| `API_PORT` | `8080` | Port where the Java API will listen |
| `PIVOT_ENGINE_BASE_URL` | `http://localhost:8000` | URL of the Python Pivot Engine service |
| `XML_API_BASE_URL` | `http://localhost:8001` | URL of the Python XML Engine service |
| `PIVOT_API_PATH` | `/pivot` | Path for the pivot API endpoint |
| `XML_GENERATE_PATH` | `/generate-xml` | Path for the XML generation endpoint |
| `JAVA_OPTS` | `-Xmx512m -Xms256m` | JVM options for memory settings |

### Setting Environment Variables

**Windows (Command Prompt):**
```batch
set API_PORT=8085
set PIVOT_ENGINE_BASE_URL=http://localhost:8000
run-local.bat
```

**Windows (PowerShell):**
```powershell
$env:API_PORT="8085"
$env:PIVOT_ENGINE_BASE_URL="http://localhost:8000"
.\run-local.bat
```

**Linux/Mac:**
```bash
export API_PORT=8085
export PIVOT_ENGINE_BASE_URL=http://localhost:8000
./run-local.sh
```

## Running Python Services

The Java API depends on two Python services. You need to start them before running the Java API:

### 1. Python Pivot Engine (Port 8000)

```bash
cd python-engine
pip install -r requirements.txt
python app.py
```

### 2. Python XML Engine (Port 8001)

```bash
cd python-xml-engine
pip install -r requirements.txt
python app.py
```

The runner scripts will check if these services are running and warn you if they're not available.

## Manual Build and Run

If you prefer to build and run manually without the scripts:

### Build the Application

```bash
cd java-api
mvn clean package
```

This creates a fat JAR file at: `target/xlsx-pivot-gateway.jar`

### Run the Application

```bash
java -jar target/xlsx-pivot-gateway.jar
```

Or with custom JVM options:

```bash
java -Xmx512m -Xms256m -jar target/xlsx-pivot-gateway.jar
```

## Accessing the Application

Once the server is running, you can access:

- **Web Interface**: http://localhost:8080/
- **Health Check**: http://localhost:8080/health
- **Pivot API**: http://localhost:8080/pivot (POST)
- **XML Generation**: http://localhost:8080/generate-xml (POST)
- **Config Endpoint**: http://localhost:8080/config

## Testing the API

### Health Check

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

### Upload XLSX File (Pivot API)

```bash
curl -X POST -F "file=@path/to/your/file.xlsx" http://localhost:8080/pivot
```

## Troubleshooting

### Port Already in Use

If port 8080 is already in use, change it:

```bash
# Linux/Mac
export API_PORT=8085
./run-local.sh

# Windows
set API_PORT=8085
run-local.bat
```

### Build Failures

1. **Clear Maven cache:**
   ```bash
   mvn clean
   rm -rf ~/.m2/repository  # or delete C:\Users\YourUser\.m2\repository on Windows
   mvn package
   ```

2. **Check Java version:**
   ```bash
   java -version  # Should be 17 or higher
   ```

### Python Services Not Available

If the Python services are not running:

1. Start them manually (see "Running Python Services" section above)
2. Check if they're listening on the correct ports:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8001/health
   ```
3. Update the URLs in environment variables if they're running on different ports

### Connection Refused Errors

If you get connection refused errors to Python services:

1. Make sure Python services are running
2. Check firewall settings
3. Verify the URLs in environment variables match where services are running
4. Check if services are bound to `0.0.0.0` or `localhost`

## Development Tips

### Hot Reload (Manual)

For development, you can run in watch mode:

1. Keep the application running
2. In another terminal, rebuild:
   ```bash
   mvn package -DskipTests
   ```
3. Restart the Java process

### Debug Mode

To run with debug logging:

```bash
java -Dorg.slf4j.simpleLogger.defaultLogLevel=debug -jar target/xlsx-pivot-gateway.jar
```

### Remote Debugging

To enable remote debugging:

```bash
java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005 -jar target/xlsx-pivot-gateway.jar
```

Then connect your IDE debugger to `localhost:5005`

## Stopping the Server

Press `Ctrl+C` in the terminal where the server is running.

## Comparing with Docker

| Aspect | Local Run | Docker |
|--------|-----------|--------|
| Setup Time | Faster (no image build) | Slower (image build) |
| Resource Usage | Lower | Higher (containerization overhead) |
| Dependencies | Must install Java/Maven | Only need Docker |
| Debugging | Easier (direct access) | Requires container access |
| Production-like | Less similar | More similar |

## Additional Resources

- [Takes Framework Documentation](https://www.takes.org/)
- [Maven Documentation](https://maven.apache.org/guides/)
- [Java 17 Documentation](https://docs.oracle.com/en/java/javase/17/)

## Support

For issues or questions, check the main project documentation or contact the development team.