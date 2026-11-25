"""Regenerate the sample data files in ./data (dates are relative to today)."""
from pathlib import Path

from core.sample_data import write_sample_files

if __name__ == "__main__":
    for path in write_sample_files(Path(__file__).parent / "data"):
        print("wrote", path)
