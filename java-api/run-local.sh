#!/bin/bash

# Script to run Java API locally without Docker
# This script builds the Java application and runs it with proper environment variables

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Java API Local Runner ===${NC}"
echo ""

# Check if Java is installed
if ! command -v java &> /dev/null; then
    echo -e "${RED}Error: Java is not installed or not in PATH${NC}"
    echo "Please install Java 17 or higher"
    exit 1
fi

# Check Java version
JAVA_VERSION=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | awk -F '.' '{print $1}')
if [ "$JAVA_VERSION" -lt 17 ]; then
    echo -e "${RED}Error: Java 17 or higher is required${NC}"
    echo "Current Java version: $(java -version 2>&1 | head -n 1)"
    exit 1
fi

echo -e "${GREEN}✓ Java version check passed${NC}"

# Check if Maven is installed
if ! command -v mvn &> /dev/null; then
    echo -e "${RED}Error: Maven is not installed or not in PATH${NC}"
    echo "Please install Apache Maven"
    exit 1
fi

echo -e "${GREEN}✓ Maven check passed${NC}"
echo ""

# Navigate to java-api directory
cd "$(dirname "$0")"

# Default environment variables
export API_PORT="${API_PORT:-8080}"
export PIVOT_ENGINE_BASE_URL="${PIVOT_ENGINE_BASE_URL:-http://localhost:8000}"
export XML_API_BASE_URL="${XML_API_BASE_URL:-http://localhost:8001}"
export PIVOT_API_PATH="${PIVOT_API_PATH:-/pivot}"
export XML_GENERATE_PATH="${XML_GENERATE_PATH:-/generate-xml}"
export JAVA_OPTS="${JAVA_OPTS:--Xmx512m -Xms256m}"

echo -e "${YELLOW}Configuration:${NC}"
echo "  API_PORT:               $API_PORT"
echo "  PIVOT_ENGINE_BASE_URL:  $PIVOT_ENGINE_BASE_URL"
echo "  XML_API_BASE_URL:       $XML_API_BASE_URL"
echo "  PIVOT_API_PATH:         $PIVOT_API_PATH"
echo "  XML_GENERATE_PATH:      $XML_GENERATE_PATH"
echo "  JAVA_OPTS:              $JAVA_OPTS"
echo ""

# Check if Python services are running
echo -e "${YELLOW}Checking Python services...${NC}"

check_service() {
    local url=$1
    local name=$2
    if curl -s -f "$url/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ $name is running at $url${NC}"
        return 0
    else
        echo -e "${RED}✗ $name is NOT running at $url${NC}"
        return 1
    fi
}

PIVOT_RUNNING=0
XML_RUNNING=0

check_service "$PIVOT_ENGINE_BASE_URL" "Python Pivot Engine" && PIVOT_RUNNING=1 || true
check_service "$XML_API_BASE_URL" "Python XML Engine" && XML_RUNNING=1 || true

if [ $PIVOT_RUNNING -eq 0 ] || [ $XML_RUNNING -eq 0 ]; then
    echo ""
    echo -e "${YELLOW}Warning: Some Python services are not running!${NC}"
    echo "The Java API will start, but some features may not work."
    echo ""
    echo "To start Python services:"
    echo "  1. Python Pivot Engine:  cd ../python-engine && python app.py"
    echo "  2. Python XML Engine:    cd ../python-xml-engine && python app.py"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo -e "${YELLOW}Building application...${NC}"

# Clean and build with Maven
mvn clean package -DskipTests

if [ $? -ne 0 ]; then
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Build successful${NC}"
echo ""

# Find the built JAR
JAR_FILE="target/xlsx-pivot-gateway.jar"

if [ ! -f "$JAR_FILE" ]; then
    echo -e "${RED}Error: JAR file not found at $JAR_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}Starting Java API server...${NC}"
echo -e "${YELLOW}Server will be available at: http://localhost:$API_PORT${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Run the application
java $JAVA_OPTS -jar "$JAR_FILE"
