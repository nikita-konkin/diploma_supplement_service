#!/bin/bash

# Convenience script to start all services locally
# This opens each service in a new terminal window/tab

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================"
echo "Starting All Services Locally"
echo -e "========================================${NC}"
echo ""
echo "This will start 3 services:"
echo "  1. Python Pivot Engine (Port 8000)"
echo "  2. Python XML Engine (Port 8001)"
echo "  3. Java API Gateway (Port 8080)"
echo ""
echo -e "${YELLOW}Press Ctrl+C in each terminal to stop the respective service.${NC}"
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Detect OS and terminal
detect_terminal() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        echo "macos"
    elif command -v gnome-terminal &> /dev/null; then
        echo "gnome"
    elif command -v xfce4-terminal &> /dev/null; then
        echo "xfce4"
    elif command -v konsole &> /dev/null; then
        echo "konsole"
    elif command -v xterm &> /dev/null; then
        echo "xterm"
    else
        echo "unknown"
    fi
}

TERMINAL_TYPE=$(detect_terminal)

start_service() {
    local service_name=$1
    local service_dir=$2
    local service_cmd=$3
    local port=$4

    echo -e "${CYAN}Starting $service_name...${NC}"

    case $TERMINAL_TYPE in
        macos)
            osascript -e "tell app \"Terminal\" to do script \"cd '$SCRIPT_DIR/$service_dir' && echo 'Starting $service_name on port $port...' && $service_cmd\""
            ;;
        gnome)
            gnome-terminal --title="$service_name (Port $port)" -- bash -c "cd '$SCRIPT_DIR/$service_dir' && echo 'Starting $service_name on port $port...' && $service_cmd; exec bash"
            ;;
        xfce4)
            xfce4-terminal --title="$service_name (Port $port)" -e "bash -c \"cd '$SCRIPT_DIR/$service_dir' && echo 'Starting $service_name on port $port...' && $service_cmd; exec bash\""
            ;;
        konsole)
            konsole --new-tab -e bash -c "cd '$SCRIPT_DIR/$service_dir' && echo 'Starting $service_name on port $port...' && $service_cmd; exec bash" &
            ;;
        xterm)
            xterm -T "$service_name (Port $port)" -e "cd '$SCRIPT_DIR/$service_dir' && echo 'Starting $service_name on port $port...' && $service_cmd; bash" &
            ;;
        *)
            echo -e "${YELLOW}Could not detect terminal. Starting in background...${NC}"
            cd "$SCRIPT_DIR/$service_dir"
            nohup bash -c "$service_cmd" > "/tmp/${service_name// /_}.log" 2>&1 &
            echo "  Log file: /tmp/${service_name// /_}.log"
            cd "$SCRIPT_DIR"
            ;;
    esac

    sleep 2
}

# Start Python Pivot Engine
start_service "Python Pivot Engine" "python-engine" "pip install -r requirements.txt && python app.py" "8000"

# Start Python XML Engine
start_service "Python XML Engine" "python-xml-engine" "pip install -r requirements.txt && python app.py" "8001"

# Start Java API Gateway
start_service "Java API Gateway" "java-api" "./run-local.sh" "8080"

echo ""
echo -e "${GREEN}========================================"
echo "All services are starting up..."
echo -e "========================================${NC}"
echo ""
echo "Please wait for all services to fully start (about 30-60 seconds)"
echo ""
echo -e "${CYAN}Once started, access the application at:${NC}"
echo "  http://localhost:8080"
echo ""
echo -e "${CYAN}Check health endpoints:${NC}"
echo "  curl http://localhost:8080/health"
echo "  curl http://localhost:8000/health"
echo "  curl http://localhost:8001/health"
echo ""

if [[ "$TERMINAL_TYPE" == "unknown" ]]; then
    echo -e "${YELLOW}Services are running in background.${NC}"
    echo "To stop them, use: pkill -f 'python app.py' && pkill -f 'java.*xlsx-pivot-gateway'"
    echo ""
    echo "View logs at:"
    echo "  /tmp/Python_Pivot_Engine.log"
    echo "  /tmp/Python_XML_Engine.log"
    echo "  /tmp/Java_API_Gateway.log"
else
    echo -e "${YELLOW}Services are running in separate terminal windows/tabs.${NC}"
    echo "Press Ctrl+C in each terminal to stop the respective service."
fi

echo ""
echo -e "${GREEN}Startup complete!${NC}"
