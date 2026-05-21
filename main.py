"""GUI entry point. Run: python main.py"""
import multiprocessing
from gui.main_window import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for PyInstaller + multiprocessing on Windows
    main()
