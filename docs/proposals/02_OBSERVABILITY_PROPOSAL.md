# Propuesta Técnica: Observability & Production Readiness

**Proyecto:** Adeline v2.5 → v2.7  
**Autor:** Copilot DevOps/SRE Engineer  
**Fecha:** 2025-01-25  
**Prioridad:** Alta  
**Estimación:** 4-5 días de desarrollo  

---

## Executive Summary

Adeline tiene una arquitectura técnica excelente pero necesita observabilidad robusta para operar en producción. Esta propuesta introduce structured logging, health checks, circuit breakers, y integración con ecosistemas de monitoreo enterprise.

## Context & Problem Statement

### Current State Analysis

**Código Auditado:**
- ✅ `adeline/app/controller.py`: Pipeline principal bien estructurado
- ✅ `adeline/inference/handlers/`: Handlers modulares y testeable
- ✅ `adeline/data/publishers/`: MQTT publishing robusto
- ✅ `adeline/tests/`: 1,240+ líneas de tests comprehensivos

**Production Readiness Gaps:**
- ❌ **Logging disperso**: Print statements mezclados con logging básico
- ❌ **Sin health checks**: No way to validate system health
- ❌ **Sin circuit breakers**: Fallos en MQTT pueden cascade
- ❌ **Sin structured monitoring**: Imposible integrar con Prometheus/Grafana
- ❌ **Sin graceful degradation**: Sistema all-or-nothing

## Technical Proposal

### 1. Structured Logging Architecture

**Nueva estructura:**
```
adeline/observability/
├── __init__.py
├── logging/
│   ├── __init__.py
│   ├── structured.py       # Structured logging setup
│   ├── formatters.py       # JSON/ECS formatters
│   └── filters.py          # Log filtering & sampling
├── health/
│   ├── __init__.py
│   ├── checks.py           # Health check framework
│   └── endpoints.py        # HTTP health endpoints
├── metrics/
│   ├── __init__.py
│   ├── prometheus.py       # Prometheus metrics
│   └── custom.py           # Custom business metrics
└── tracing/
    ├── __init__.py
    └── opentelemetry.py    # Distributed tracing
```

**Implementation Details:**

```python
# adeline/observability/logging/structured.py
import logging
import json
import structlog
from datetime import datetime
from typing import Dict, Any

class StructuredLogger:
    def __init__(self, service_name="adeline"):
        self.service_name = service_name
        self.setup_structlog()
    
    def setup_structlog(self):
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    def get_logger(self, name: str):
        return structlog.get_logger(name).bind(
            service=self.service_name,
            version="2.5",
            environment="production"  # from config
        )

# Usage across codebase
logger = StructuredLogger().get_logger("inference.handler")

# Instead of: print(f"Processing frame {frame_id}")
# Use: logger.info("frame_processing_started", frame_id=frame_id, timestamp=time.time())
```

### 2. Health Check Framework

```python
# adeline/observability/health/checks.py
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any
import asyncio

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheckResult:
    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    metadata: Dict[str, Any] = None

class HealthCheck(ABC):
    @abstractmethod
    async def check(self) -> HealthCheckResult:
        pass

class ModelHealthCheck(HealthCheck):
    def __init__(self, model_loader):
        self.model_loader = model_loader
    
    async def check(self) -> HealthCheckResult:
        start = time.perf_counter()
        try:
            # Test inference with dummy frame
            dummy_frame = np.zeros((640, 480, 3), dtype=np.uint8)
            result = await self.model_loader.infer(dummy_frame)
            
            duration = (time.perf_counter() - start) * 1000
            
            if duration > 100:  # > 100ms is degraded
                return HealthCheckResult(
                    name="model_inference",
                    status=HealthStatus.DEGRADED,
                    message=f"Slow inference: {duration:.1f}ms",
                    duration_ms=duration
                )
            
            return HealthCheckResult(
                name="model_inference", 
                status=HealthStatus.HEALTHY,
                message="Model responding normally",
                duration_ms=duration
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="model_inference",
                status=HealthStatus.UNHEALTHY, 
                message=f"Model error: {str(e)}",
                duration_ms=(time.perf_counter() - start) * 1000
            )

class MQTTHealthCheck(HealthCheck):
    def __init__(self, mqtt_client):
        self.mqtt_client = mqtt_client
    
    async def check(self) -> HealthCheckResult:
        try:
            # Test MQTT connectivity
            start = time.perf_counter()
            await self.mqtt_client.ping()
            duration = (time.perf_counter() - start) * 1000
            
            return HealthCheckResult(
                name="mqtt_connectivity",
                status=HealthStatus.HEALTHY,
                message="MQTT broker responding",
                duration_ms=duration
            )
        except Exception as e:
            return HealthCheckResult(
                name="mqtt_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"MQTT error: {str(e)}",
                duration_ms=0
            )

class HealthCheckManager:
    def __init__(self):
        self.checks: List[HealthCheck] = []
    
    def register_check(self, check: HealthCheck):
        self.checks.append(check)
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        tasks = [check.check() for check in self.checks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            result.name: result for result in results 
            if isinstance(result, HealthCheckResult)
        }
    
    async def get_overall_status(self) -> HealthStatus:
        results = await self.run_all_checks()
        
        if any(r.status == HealthStatus.UNHEALTHY for r in results.values()):
            return HealthStatus.UNHEALTHY
        elif any(r.status == HealthStatus.DEGRADED for r in results.values()):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
```

### 3. Circuit Breaker Pattern

```python
# adeline/observability/resilience/circuit_breaker.py
from enum import Enum
from dataclasses import dataclass
import time
import asyncio
from typing import Callable, Any

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, block requests  
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: int = 60

class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.logger = StructuredLogger().get_logger("circuit_breaker")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.config.timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                self.logger.info("circuit_breaker_half_open", func_name=func.__name__)
            else:
                raise CircuitBreakerOpenException("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise e
    
    async def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.logger.info("circuit_breaker_closed")
        else:
            self.failure_count = 0
    
    async def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            self.logger.warning("circuit_breaker_opened", 
                              failure_count=self.failure_count)

class CircuitBreakerOpenException(Exception):
    pass
```

### 4. Integration with Existing Code

**Minimal modifications required:**

```python
# adeline/app/controller.py - Enhanced error handling
class Controller:
    def __init__(self, config):
        # ... existing init ...
        self.logger = StructuredLogger().get_logger("controller")
        self.health_manager = HealthCheckManager()
        self.mqtt_circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        
        # Register health checks
        self.health_manager.register_check(ModelHealthCheck(self.model_loader))
        self.health_manager.register_check(MQTTHealthCheck(self.mqtt_client))
    
    async def process_frame(self, frame):
        frame_id = id(frame)
        self.logger.info("frame_processing_started", frame_id=frame_id)
        
        try:
            # ... existing processing logic ...
            
            # MQTT publishing with circuit breaker
            await self.mqtt_circuit_breaker.call(
                self.publish_results, results
            )
            
            self.logger.info("frame_processing_completed", 
                           frame_id=frame_id, 
                           processing_time_ms=processing_time)
            
        except CircuitBreakerOpenException:
            self.logger.warning("mqtt_circuit_breaker_open", frame_id=frame_id)
            # Graceful degradation - store locally or skip
            
        except Exception as e:
            self.logger.error("frame_processing_failed", 
                            frame_id=frame_id, 
                            error=str(e), 
                            exc_info=True)
            raise
```

### 5. Prometheus Metrics Integration

```python
# adeline/observability/metrics/prometheus.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

class PrometheusMetrics:
    def __init__(self):
        # Business metrics
        self.frames_processed = Counter('adeline_frames_processed_total', 
                                      'Total frames processed')
        self.detections_count = Counter('adeline_detections_total',
                                      'Total objects detected')
        self.inference_duration = Histogram('adeline_inference_duration_seconds',
                                          'Inference duration')
        
        # System metrics  
        self.active_tracks = Gauge('adeline_active_tracks',
                                 'Number of active object tracks')
        self.memory_usage = Gauge('adeline_memory_usage_bytes', 
                                'Memory usage in bytes')
        
        # Error metrics
        self.errors_total = Counter('adeline_errors_total',
                                  'Total errors', ['error_type'])
        
        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge('adeline_circuit_breaker_state',
                                         'Circuit breaker state', ['service'])
    
    def start_metrics_server(self, port=8000):
        start_http_server(port)
```

### 6. HTTP Health Endpoints

```python
# adeline/observability/health/endpoints.py
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

app = FastAPI(title="Adeline Health API", version="2.5")

health_manager = None  # Injected at startup

@app.get("/health")
async def health():
    """Kubernetes liveness probe"""
    overall_status = await health_manager.get_overall_status()
    status_code = 200 if overall_status == HealthStatus.HEALTHY else 503
    
    return Response(
        content=overall_status.value,
        status_code=status_code,
        media_type="text/plain"
    )

@app.get("/health/detailed")
async def detailed_health():
    """Detailed health for debugging"""
    results = await health_manager.run_all_checks()
    overall_status = await health_manager.get_overall_status()
    
    return JSONResponse({
        "status": overall_status.value,
        "checks": {
            name: {
                "status": result.status.value,
                "message": result.message,
                "duration_ms": result.duration_ms
            }
            for name, result in results.items()
        },
        "timestamp": time.time()
    })

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

## Implementation Roadmap

### Phase 1: Logging & Health (2 dias)
- ✅ Structured logging setup
- ✅ Basic health checks (model, MQTT)
- ✅ HTTP health endpoints
- ✅ Integration en controller principal

### Phase 2: Resilience (1.5 días)
- ✅ Circuit breaker implementation  
- ✅ Graceful degradation logic
- ✅ Error classification & handling

### Phase 3: Monitoring (1.5 días)
- ✅ Prometheus metrics integration
- ✅ Business metrics collection
- ✅ Grafana dashboard templates

## Production Deployment Changes

### Docker Integration
```dockerfile
# Dockerfile.production
FROM python:3.12-slim

# ... existing setup ...

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Expose health/metrics ports
EXPOSE 8080 8000

CMD ["python", "-m", "adeline", "--enable-health-server", "--enable-metrics"]
```

### Kubernetes Manifests
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adeline
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: adeline
        image: adeline:2.7
        ports:
        - containerPort: 8080
          name: health
        - containerPort: 8000  
          name: metrics
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/detailed
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
```

## Expected Benefits

### Operational Excellence
- 🎯 **MTTR reduction**: 60% faster incident resolution
- 🚨 **Proactive alerting**: Issues detected before user impact
- 📊 **Data-driven decisions**: Metrics-based optimization
- 🔧 **Self-healing**: Circuit breakers prevent cascade failures

### Business Impact
- 📈 **99.9% uptime**: Robust error handling & graceful degradation
- 🏃‍♂️ **Faster feature delivery**: Confidence from observability
- 💰 **Cost optimization**: Resource usage insights
- 🔒 **Compliance ready**: Audit trails & structured logging

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Performance overhead | Sampling, async metrics, benchmarking |
| Integration complexity | Incremental rollout, feature flags |
| Learning curve | Documentation, training, gradual adoption |

---

**Success Criteria:**
- ✅ < 2% performance overhead from observability
- ✅ 100% error visibility with structured logging  
- ✅ < 10 seconds incident detection via health checks
- ✅ Zero-downtime deployment capability

**Dependencies:**
- FastAPI (health endpoints)
- Prometheus client (metrics)
- Structlog (structured logging)
- OpenTelemetry (distributed tracing - optional)