# Adeline - Inference Pipeline with MQTT Control

Sistema de inferencia de visión por computadora (YOLO) con control remoto MQTT.

## 🚀 Quick Start

### Setup

```bash
# Install dependencies
make install

# Start infrastructure services (MQTT broker + go2rtc)
make services-up

# Run pipeline
make run
```

### Control Commands (in another terminal)

```bash
make pause          # Pause processing
make resume         # Resume processing
make status         # Check status
make metrics        # Get performance metrics
make stop           # Stop pipeline
```

See `make help` for all available commands!

## 📦 Main Commands

| Command | Description |
|---------|-------------|
| `make run` | Run inference pipeline |
| `make stop` | Stop pipeline via MQTT |
| `make pause` / `make resume` | Control processing |
| `make monitor-data` | Monitor detection stream |
| `make services-up` / `make services-down` | Manage infrastructure |

## 🏗️ Architecture

Ver [DESIGN.md](DESIGN.md) para detalles completos de la arquitectura 4+1.

## 📚 Documentation

- [DESIGN.md](DESIGN.md) - Arquitectura 4+1 completa
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Guía de migración
- [Makefile](../Makefile) - Todos los comandos disponibles

Run `make help` for complete command reference.
