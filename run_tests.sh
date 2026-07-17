#!/bin/bash
cd /c/Users/shobhasreenivas/multi-agent-research-lab
python -m pytest tests/unit/ -v --tb=short 2>&1 | head -100