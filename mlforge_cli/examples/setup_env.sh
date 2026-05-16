#!/bin/bash

# MLForge CLI Automation Example
# This script demonstrates a typical setup workflow.

echo "--- 🛠️ Initializing MLForge Environment ---"

# 1. Check system telemetry
mlforge system

# 2. Check login status
mlforge whoami

# 3. List local datasets to see if we need more
echo "Checking datasets..."
mlforge dataset list

# 4. Explore models and download a lightweight one if not present
echo "Ensuring YOLOv8n is cached..."
mlforge explore download yolov8n

# 5. List all active runs
echo "Recent training activity:"
mlforge train runs --limit 5

echo "--- ✅ Environment Ready ---"
