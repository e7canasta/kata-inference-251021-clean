# Propuesta Técnica: Configuration Validation & Type Safety

**Proyecto:** Adeline v2.5 → v2.6  
**Autor:** Copilot Configuration Engineer  
**Fecha:** 2025-01-25  
**Prioridad:** Media-Alta  
**Estimación:** 2-3 días de desarrollo  

---

## Executive Summary

Adeline tiene una base sólida de configuración con Pydantic, pero necesita validación más robusta y type safety completo. Esta propuesta introduce validación avanzada, configuration profiles, y type hints comprehensivos para eliminar errores de configuración en tiempo de despliegue.

## Current State Analysis

### Existing Configuration Audit

**Files Reviewed:**
- ✅ `adeline/config/schemas.py`: Pydantic schemas básicos presentes
- ✅ `adeline/legacy_config.py`: Legacy config que debe ser migrado
- ✅ `adeline/test_pydantic_validation.py`: Tests básicos presentes

**Current Strengths:**
- ✅ **Pydantic foundation**: Base configuration schemas defined
- ✅ **Type hints present**: Basic typing in place
- ✅ **Environment variables**: Support for env-based config

**Critical Gaps Identified:**
- ❌ **Incomplete validation**: No cross-field validation
- ❌ **No configuration profiles**: Dev/Test/Prod configs mixed
- ❌ **Missing runtime validation**: Config changes not validated
- ❌ **Type safety gaps**: Any types in factories and handlers
- ❌ **No configuration versioning**: Schema evolution not managed

## Technical Proposal

### 1. Enhanced Configuration Schema

**New file structure:**
```
adeline/config/
├── __init__.py
├── schemas/
│   ├── __init__.py
│   ├── base.py              # Base configuration
│   ├── inference.py         # Inference-specific config
│   ├── networking.py        # MQTT/network config
│   ├── performance.py       # Performance tuning config
│   └── validation.py        # Cross-field validators
├── profiles/
│   ├── __init__.py
│   ├── development.py       # Dev environment config
│   ├── testing.py           # Test environment config
│   ├── staging.py           # Staging environment config
│   └── production.py        # Production environment config
├── loaders/
│   ├── __init__.py
│   ├── file_loader.py       # File-based config loading
│   ├── env_loader.py        # Environment variable loading
│   └── remote_loader.py     # Remote config (future)
└── validators/
    ├── __init__.py
    ├── business.py          # Business logic validators
    ├── performance.py       # Performance constraint validators
    └── security.py          # Security validators
```

### 2. Enhanced Pydantic Schemas

```python
# adeline/config/schemas/base.py
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Literal, Optional, Union, List
from enum import Enum
import os
from pathlib import Path

class EnvironmentType(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing" 
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class BaseConfiguration(BaseModel):
    """Base configuration with common settings."""
    
    model_config = ConfigDict(
        env_prefix="ADELINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        validate_assignment=True,  # Validate on attribute assignment
        frozen=True,  # Immutable configuration
        extra="forbid"  # Forbid extra fields
    )
    
    # Environment settings
    environment: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        description="Deployment environment"
    )
    
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    
    # Application settings
    app_name: str = Field(
        default="adeline",
        min_length=1,
        max_length=50,
        pattern=r'^[a-zA-Z0-9_-]+$',
        description="Application name"
    )
    
    version: str = Field(
        default="2.5.0",
        pattern=r'^\d+\.\d+\.\d+$',
        description="Application version"
    )
    
    @field_validator('debug')
    @classmethod
    def validate_debug_environment(cls, v: bool, values) -> bool:
        """Debug should not be enabled in production."""
        if hasattr(values, 'environment') and values.environment == EnvironmentType.PRODUCTION and v:
            raise ValueError("Debug mode cannot be enabled in production environment")
        return v
```

```python
# adeline/config/schemas/inference.py
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import torch

class ModelConfiguration(BaseModel):
    """Model-specific configuration with validation."""
    
    model_path: Path = Field(
        description="Path to the inference model file"
    )
    
    model_type: Literal["yolo", "detectron2", "custom"] = Field(
        default="yolo",
        description="Type of model architecture"
    )
    
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for detections"
    )
    
    nms_threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Non-maximum suppression threshold"
    )
    
    max_detections: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of detections per frame"
    )
    
    device: str = Field(
        default="auto",
        description="Inference device: 'cpu', 'cuda', 'auto'"
    )
    
    batch_size: int = Field(
        default=1,
        ge=1,
        le=64,
        description="Inference batch size"
    )
    
    @field_validator('model_path')
    @classmethod
    def validate_model_exists(cls, v: Path) -> Path:
        """Validate that model file exists."""
        if not v.exists():
            raise ValueError(f"Model file does not exist: {v}")
        if not v.is_file():
            raise ValueError(f"Model path is not a file: {v}")
        return v
    
    @field_validator('device')
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Validate device availability."""
        if v == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        elif v == "cuda":
            if not torch.cuda.is_available():
                raise ValueError("CUDA not available but cuda device specified")
        elif v != "cpu":
            raise ValueError(f"Invalid device: {v}. Must be 'cpu', 'cuda', or 'auto'")
        return v
    
    @model_validator(mode='after')
    def validate_performance_constraints(self) -> 'ModelConfiguration':
        """Cross-field validation for performance constraints."""
        if self.batch_size > 1 and self.device == "cpu":
            raise ValueError("Batch size > 1 not recommended for CPU inference")
        
        if self.max_detections > 500 and self.batch_size > 1:
            raise ValueError("High max_detections with batching may cause memory issues")
        
        return self

class ROIConfiguration(BaseModel):
    """ROI (Region of Interest) configuration."""
    
    mode: Literal["fixed", "adaptive", "disabled"] = Field(
        default="adaptive",
        description="ROI mode"
    )
    
    # Fixed ROI settings
    fixed_regions: Optional[List[Dict[str, Union[int, float]]]] = Field(
        default=None,
        description="Fixed ROI regions for 'fixed' mode"
    )
    
    # Adaptive ROI settings
    adaptation_rate: float = Field(
        default=0.1,
        ge=0.01,
        le=1.0,
        description="ROI adaptation rate for 'adaptive' mode"
    )
    
    min_size: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Minimum ROI size in pixels"
    )
    
    max_size: int = Field(
        default=800,
        ge=100,
        le=2000,
        description="Maximum ROI size in pixels"
    )
    
    @model_validator(mode='after')
    def validate_roi_settings(self) -> 'ROIConfiguration':
        """Validate ROI configuration consistency."""
        if self.mode == "fixed" and not self.fixed_regions:
            raise ValueError("Fixed ROI mode requires fixed_regions to be specified")
        
        if self.mode == "adaptive" and self.min_size >= self.max_size:
            raise ValueError("min_size must be less than max_size for adaptive ROI")
        
        return self

class StabilizationConfiguration(BaseModel):
    """Object tracking stabilization configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Enable object tracking stabilization"
    )
    
    strategy: Literal["iou", "centroid", "hierarchical"] = Field(
        default="hierarchical",
        description="Tracking strategy"
    )
    
    iou_threshold: float = Field(
        default=0.5,
        ge=0.1,
        le=0.9,
        description="IoU threshold for matching"
    )
    
    max_disappeared: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Max frames before track is considered lost"
    )
    
    min_track_length: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Minimum track length for stability"
    )

class InferenceConfiguration(BaseModel):
    """Complete inference configuration."""
    
    model: ModelConfiguration
    roi: ROIConfiguration
    stabilization: StabilizationConfiguration
    
    # Performance settings
    max_fps: Optional[float] = Field(
        default=None,
        gt=0,
        le=120,
        description="Maximum processing FPS (None for unlimited)"
    )
    
    enable_async: bool = Field(
        default=True,
        description="Enable async processing"
    )
    
    worker_threads: int = Field(
        default=1,
        ge=1,
        le=16,
        description="Number of worker threads"
    )
```

### 3. Configuration Profiles

```python
# adeline/config/profiles/production.py
from ..schemas.base import BaseConfiguration, EnvironmentType, LogLevel
from ..schemas.inference import InferenceConfiguration, ModelConfiguration, ROIConfiguration, StabilizationConfiguration
from ..schemas.networking import NetworkConfiguration

class ProductionConfiguration(BaseConfiguration):
    """Production environment configuration."""
    
    # Override base settings for production
    environment: EnvironmentType = EnvironmentType.PRODUCTION
    debug: bool = False
    log_level: LogLevel = LogLevel.INFO
    
    # Production-specific validation
    @model_validator(mode='after')
    def validate_production_settings(self) -> 'ProductionConfiguration':
        """Additional validation for production environment."""
        if self.debug:
            raise ValueError("Debug mode not allowed in production")
        
        if self.log_level == LogLevel.DEBUG:
            raise ValueError("Debug logging not allowed in production")
        
        return self

class ProductionInferenceConfiguration(InferenceConfiguration):
    """Production-optimized inference configuration."""
    
    # Override for production constraints
    model: ModelConfiguration = Field(
        default_factory=lambda: ModelConfiguration(
            model_path=Path("/models/production/model.pt"),
            confidence_threshold=0.7,  # Higher threshold for production
            device="cuda",  # Assume GPU in production
            batch_size=1  # Conservative batch size
        )
    )
    
    # Performance optimizations
    max_fps: float = Field(
        default=30.0,
        description="Target FPS for production"
    )
    
    worker_threads: int = Field(
        default=4,
        description="Optimal worker threads for production"
    )
```

### 4. Enhanced Type Safety

```python
# adeline/config/types.py
from typing import TypeVar, Generic, Protocol, runtime_checkable
from pydantic import BaseModel

ConfigT = TypeVar('ConfigT', bound=BaseModel)

@runtime_checkable
class Configurable(Protocol[ConfigT]):
    """Protocol for components that require configuration."""
    
    def configure(self, config: ConfigT) -> None:
        """Configure the component with typed configuration."""
        ...

# Usage in existing code:
class InferenceHandler(Configurable[InferenceConfiguration]):
    def __init__(self):
        self.config: Optional[InferenceConfiguration] = None
    
    def configure(self, config: InferenceConfiguration) -> None:
        self.config = config
        # Type-safe access to config properties
        self.confidence_threshold = config.model.confidence_threshold
```

### 5. Configuration Loading & Validation

```python
# adeline/config/loaders/manager.py
from typing import Type, TypeVar, Optional, Dict, Any
from pathlib import Path
import os
from ..schemas.base import BaseConfiguration, EnvironmentType

ConfigType = TypeVar('ConfigType', bound=BaseConfiguration)

class ConfigurationManager:
    """Centralized configuration management."""
    
    def __init__(self):
        self.loaded_configs: Dict[str, BaseConfiguration] = {}
        self.environment = self._detect_environment()
    
    def _detect_environment(self) -> EnvironmentType:
        """Auto-detect environment from various sources."""
        env_name = os.getenv("ENVIRONMENT", os.getenv("ENV", "development"))
        try:
            return EnvironmentType(env_name.lower())
        except ValueError:
            return EnvironmentType.DEVELOPMENT
    
    def load_config(
        self, 
        config_class: Type[ConfigType],
        config_file: Optional[Path] = None,
        override_values: Optional[Dict[str, Any]] = None
    ) -> ConfigType:
        """Load and validate configuration."""
        
        # Build configuration from multiple sources
        config_data = {}
        
        # 1. Load from environment-specific profile
        profile_data = self._load_profile(config_class)
        config_data.update(profile_data)
        
        # 2. Load from file if provided
        if config_file and config_file.exists():
            file_data = self._load_from_file(config_file)
            config_data.update(file_data)
        
        # 3. Apply overrides
        if override_values:
            config_data.update(override_values)
        
        # 4. Create and validate configuration
        try:
            config = config_class(**config_data)
            self.loaded_configs[config_class.__name__] = config
            return config
        except Exception as e:
            raise ConfigurationError(f"Failed to load {config_class.__name__}: {e}") from e
    
    def _load_profile(self, config_class: Type[ConfigType]) -> Dict[str, Any]:
        """Load environment-specific profile."""
        profile_map = {
            EnvironmentType.DEVELOPMENT: "development",
            EnvironmentType.TESTING: "testing", 
            EnvironmentType.STAGING: "staging",
            EnvironmentType.PRODUCTION: "production"
        }
        
        profile_name = profile_map[self.environment]
        try:
            module = __import__(f"adeline.config.profiles.{profile_name}", fromlist=[profile_name])
            profile_class = getattr(module, f"{profile_name.title()}Configuration")
            
            if issubclass(profile_class, config_class):
                return profile_class().model_dump()
        except (ImportError, AttributeError):
            pass
        
        return {}
    
    def validate_runtime_config(self, config: BaseConfiguration) -> bool:
        """Validate configuration at runtime."""
        try:
            # Re-validate the configuration
            config.__class__(**config.model_dump())
            return True
        except Exception:
            return False

class ConfigurationError(Exception):
    """Configuration-related errors."""
    pass
```

### 6. Integration with Existing Code

**Minimal changes to existing files:**

```python
# adeline/app/controller.py - Enhanced with typed configuration
from ..config.loaders.manager import ConfigurationManager
from ..config.schemas.inference import InferenceConfiguration
from ..config.types import Configurable

class Controller(Configurable[InferenceConfiguration]):
    def __init__(self, config_file: Optional[Path] = None):
        self.config_manager = ConfigurationManager()
        self.config = self.config_manager.load_config(
            InferenceConfiguration,
            config_file=config_file
        )
        
        # Type-safe configuration access
        self.model_path = self.config.model.model_path
        self.confidence_threshold = self.config.model.confidence_threshold
        self.roi_mode = self.config.roi.mode
        
        # Initialize components with typed configuration
        self.inference_handler = self._create_inference_handler()
    
    def _create_inference_handler(self) -> InferenceHandler:
        """Create inference handler with validated configuration."""
        handler = InferenceHandler()
        handler.configure(self.config)
        return handler
```

### 7. Configuration Testing

```python
# adeline/tests/test_configuration_validation.py
import pytest
from pathlib import Path
from adeline.config.schemas.inference import ModelConfiguration, InferenceConfiguration
from adeline.config.loaders.manager import ConfigurationManager, ConfigurationError

class TestModelConfiguration:
    """Test model configuration validation."""
    
    def test_valid_model_config(self):
        """Test valid model configuration."""
        config = ModelConfiguration(
            model_path=Path(__file__).parent / "fixtures" / "dummy_model.pt",
            confidence_threshold=0.7,
            device="cpu"
        )
        assert config.confidence_threshold == 0.7
        assert config.device == "cpu"
    
    def test_invalid_confidence_threshold(self):
        """Test invalid confidence threshold."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            ModelConfiguration(
                model_path=Path(__file__),
                confidence_threshold=-0.1
            )
    
    def test_nonexistent_model_path(self):
        """Test validation of nonexistent model path."""
        with pytest.raises(ValueError, match="Model file does not exist"):
            ModelConfiguration(
                model_path=Path("/nonexistent/model.pt")
            )
    
    def test_cuda_validation_without_gpu(self):
        """Test CUDA device validation when GPU not available."""
        # Mock torch.cuda.is_available to return False
        with pytest.raises(ValueError, match="CUDA not available"):
            ModelConfiguration(
                model_path=Path(__file__),
                device="cuda"
            )

class TestConfigurationManager:
    """Test configuration management."""
    
    def test_load_development_config(self, monkeypatch):
        """Test loading development configuration."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        
        manager = ConfigurationManager()
        config = manager.load_config(InferenceConfiguration)
        
        assert config.model.device in ["cpu", "cuda"]
        assert 0.0 <= config.model.confidence_threshold <= 1.0
    
    def test_configuration_validation_error(self):
        """Test configuration validation error handling."""
        manager = ConfigurationManager()
        
        with pytest.raises(ConfigurationError):
            manager.load_config(
                InferenceConfiguration,
                override_values={
                    "model": {"confidence_threshold": 1.5}  # Invalid
                }
            )
```

## Implementation Plan

### Phase 1: Core Schema Enhancement (1 día)
- ✅ Enhanced Pydantic schemas with validation
- ✅ Type safety improvements
- ✅ Cross-field validators

### Phase 2: Configuration Profiles (1 día)
- ✅ Environment-specific profiles
- ✅ Configuration manager
- ✅ Runtime validation

### Phase 3: Integration & Testing (1 día)  
- ✅ Integration with existing code
- ✅ Comprehensive test suite
- ✅ Documentation updates

## Expected Benefits

### Development Experience
- 🎯 **Faster debugging**: Configuration errors caught at startup
- 🔒 **Type safety**: IDE autocompletion and type checking
- 🧪 **Better testing**: Environment-specific configuration testing
- 📚 **Self-documenting**: Configuration schema serves as documentation

### Operational Benefits
- 🚫 **Reduced misconfigurations**: Validation prevents invalid configs
- 🔄 **Environment consistency**: Profiles ensure proper settings per environment
- 🛡️ **Security**: Validation prevents dangerous configuration combinations
- 📊 **Monitoring**: Configuration changes tracked and validated

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking changes | Backward compatibility layer, gradual migration |
| Performance overhead | Lazy validation, configuration caching |
| Complexity increase | Comprehensive documentation, examples |

---

**Success Criteria:**
- ✅ 100% type safety in configuration layer
- ✅ Zero production configuration errors
- ✅ < 50ms configuration load time
- ✅ Environment-specific configuration validation

**Dependencies:**
- Pydantic v2 (already present)
- PyTorch (for device validation)
- pathlib (standard library)