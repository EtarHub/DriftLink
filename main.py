import sys
from drivers.win_divert import start_windows_engine
from ui.app import start_app

if __name__ == "__main__":
    if "--cli" in sys.argv:
        start_windows_engine()
    else:
        start_app()
