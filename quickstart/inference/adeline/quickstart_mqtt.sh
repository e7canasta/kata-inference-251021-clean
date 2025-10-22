#!/bin/bash

# Quickstart para InferencePipeline con MQTT
# ==========================================

set -e

echo "🚀 InferencePipeline MQTT Quickstart"
echo "====================================="
echo ""

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar dependencias
echo -e "${BLUE}1. Checking dependencies...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Dependencies OK${NC}"
echo ""

# Iniciar MQTT broker
echo -e "${BLUE}2. Starting MQTT broker...${NC}"
docker-compose -f docker-compose.mqtt.yml up -d

# Esperar a que el broker esté listo
echo "Waiting for broker to be ready..."
sleep 3

if ! docker ps | grep -q mqtt-broker; then
    echo -e "${RED}❌ MQTT broker failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}✅ MQTT broker running${NC}"
echo ""

# Verificar conectividad
echo -e "${BLUE}3. Testing MQTT connection...${NC}"
if command -v mosquitto_pub &> /dev/null; then
    if mosquitto_pub -h localhost -t test -m "hello" -q 1; then
        echo -e "${GREEN}✅ MQTT connection OK${NC}"
    else
        echo -e "${YELLOW}⚠️ Could not connect to MQTT. Check if port 1883 is available.${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ mosquitto-clients not installed. Skipping test.${NC}"
    echo "   Install with: sudo apt-get install mosquitto-clients"
fi
echo ""

# Instrucciones
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Install Python dependencies:"
echo "   ${BLUE}uv sync${NC}"
echo ""
echo "2. Start the pipeline:"
echo "   ${BLUE}python run_pipeline_mqtt.py${NC}"
echo ""
echo "3. In another terminal, send commands:"
echo "   ${BLUE}python mqtt_control_cli.py start${NC}"
echo "   ${BLUE}python mqtt_control_cli.py stop${NC}"
echo ""
echo "4. Monitor detections:"
echo "   ${BLUE}python mqtt_data_monitor.py${NC}"
echo ""
echo "5. Or use mosquitto clients:"
echo "   ${BLUE}mosquitto_sub -h localhost -t inference/data/detections${NC}"
echo ""
echo -e "${YELLOW}To stop the MQTT broker:${NC}"
echo "   ${BLUE}docker-compose -f docker-compose.mqtt.yml down${NC}"
echo ""
echo "📚 See README_MQTT.md for full documentation"

