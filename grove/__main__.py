"""grove/__main__.py — Entry point: python3 -m grove
b17: WDASH  ΔΣ=42
"""
import curses
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grove.shell import Shell
from grove.apps.vitals import VitalsApp
from grove.apps.chat import ChatApp
from grove.apps.models import ModelsApp


def main():
    chat   = ChatApp()
    models = ModelsApp()
    vitals = VitalsApp()

    shell = Shell(apps=[chat, models], vitals_app=vitals)

    try:
        curses.wrapper(shell.run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
