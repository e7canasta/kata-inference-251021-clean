"""
Adeline Test Suite
==================

Property-based tests for critical invariants.

Philosophy:
- Focus on invariants (properties that must always be true)
- Test critical paths (MQTT, pipeline lifecycle)
- NOT 100% coverage - only key behaviors

Modules:
- test_roi: ROI invariants (square, expand, transforms)
- test_mqtt_commands: MQTT control commands
- test_stabilization: Stabilization logic
"""
