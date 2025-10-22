  Key sections included:

  Running the Application: Commands to run the pipeline, control CLI, and monitors

  Architecture Overview:
  - Control/Data plane separation pattern with different MQTT QoS strategies
  - Core components and their responsibilities
  - Critical initialization order for model disabling

  Inference Features:
  - ROI strategies (adaptive/fixed) with factory pattern
  - Detection stabilization to reduce flickering
  - Model management (Roboflow API vs local ONNX)

  Design Principles:
  - Emphasized "complexity by design" (from parent CLAUDE.md)
  - MQTT QoS strategy rationale
  - Configuration-driven architecture

  Common Patterns:
  - Multi-sink pattern
  - Factory patterns for strategies
  - MQTT command format

  The file focuses on the "big picture" architecture that requires reading multiple files to understand, avoiding obvious details that can be easily discovered through code exploration.
