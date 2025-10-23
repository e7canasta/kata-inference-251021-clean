"""
Adeline Inference Pipeline
==========================

Fall detection system for geriatric residences.

This package provides a complete YOLO-based inference pipeline with:
- Adaptive ROI (Region of Interest) processing
- Detection stabilization (temporal hysteresis)
- Dual-plane MQTT architecture (Control + Data)
- Multi-object tracking with IoU matching
"""

__version__ = "3.0.0"
__author__ = "Visiona Team"

__all__ = [
    '__version__',
    '__author__',
]
