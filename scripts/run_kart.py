#!/usr/bin/env python3
"""Entrypoint for the kart-worker systemd service."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from core.kart_worker import kart_loop

kart_loop()
