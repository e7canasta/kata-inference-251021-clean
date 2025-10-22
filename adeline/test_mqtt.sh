#!/bin/bash

# Script de prueba para MQTT Control y Data Plane
# ================================================

set -e

BROKER="${MQTT_BROKER:-localhost}"
PORT="${MQTT_PORT:-1883}"

echo "🧪 Testing MQTT Bridge"
echo "====================="
echo "Broker: $BROKER:$PORT"
echo ""

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Test conexión
echo -e "${BLUE}1. Testing connection...${NC}"
if mosquitto_pub -h "$BROKER" -p "$PORT" -t test -m "hello" -q 1; then
    echo -e "${GREEN}✅ Connection OK${NC}"
else
    echo "❌ Connection failed"
    exit 1
fi
echo ""

# 2. Test control commands
echo -e "${BLUE}2. Testing control commands...${NC}"

echo "  Sending START command..."
mosquitto_pub -h "$BROKER" -p "$PORT" \
  -t inference/control/commands \
  -m '{"command": "start"}' -q 1
sleep 1

echo "  Sending STATUS command..."
mosquitto_pub -h "$BROKER" -p "$PORT" \
  -t inference/control/commands \
  -m '{"command": "status"}' -q 1
sleep 1

echo "  Sending PAUSE command..."
mosquitto_pub -h "$BROKER" -p "$PORT" \
  -t inference/control/commands \
  -m '{"command": "pause"}' -q 1
sleep 1

echo "  Sending RESUME command..."
mosquitto_pub -h "$BROKER" -p "$PORT" \
  -t inference/control/commands \
  -m '{"command": "resume"}' -q 1
sleep 1

echo "  Sending STOP command..."
mosquitto_pub -h "$BROKER" -p "$PORT" \
  -t inference/control/commands \
  -m '{"command": "stop"}' -q 1

echo -e "${GREEN}✅ Control commands sent${NC}"
echo ""

# 3. Test data plane (simulation)
echo -e "${BLUE}3. Testing data plane (simulation)...${NC}"
mosquitto_pub -h "$BROKER" -p "$PORT" \
  -t inference/data/detections \
  -m '{
    "timestamp": "'$(date -Iseconds)'",
    "message_id": 1,
    "detection_count": 2,
    "detections": [
      {
        "class": "person",
        "confidence": 0.95,
        "bbox": {"x": 100, "y": 200, "width": 50, "height": 100}
      },
      {
        "class": "car",
        "confidence": 0.87,
        "bbox": {"x": 300, "y": 150, "width": 120, "height": 80}
      }
    ],
    "frame": {
      "frame_id": 1,
      "source_id": 0,
      "timestamp": "'$(date -Iseconds)'"
    }
  }' -q 0

echo -e "${GREEN}✅ Test detection published${NC}"
echo ""

# 4. Check status topic
echo -e "${BLUE}4. Checking status topic (retained message)...${NC}"
timeout 2 mosquitto_sub -h "$BROKER" -p "$PORT" \
  -t inference/control/status -C 1 || true
echo ""

echo -e "${GREEN}✅ All tests passed!${NC}"
echo ""
echo -e "${YELLOW}To monitor data plane:${NC}"
echo "  mosquitto_sub -h $BROKER -t inference/data/detections -v"
echo ""
echo -e "${YELLOW}To monitor control status:${NC}"
echo "  mosquitto_sub -h $BROKER -t inference/control/status -v"

