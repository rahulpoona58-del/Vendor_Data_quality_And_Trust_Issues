import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.seed_demo_dataset import seed_demo_dataset, DEMO_DB_PATH

def main():
    parser = argparse.ArgumentParser(description="Demo Mode Management CLI Utility")
    parser.add_argument('action', choices=['setup', 'reset', 'status'], help="Demo action to perform")

    args = parser.parse_args()

    if args.action in ['setup', 'reset']:
        if args.action == 'reset' and DEMO_DB_PATH.exists():
            print(f"Removing existing demo database at {DEMO_DB_PATH}...")
            DEMO_DB_PATH.unlink()
        
        print("Executing One-Click Demo Mode Setup...")
        seed_demo_dataset()
        print(f"[SUCCESS] Demo Mode [{args.action.upper()}] completed successfully!")

    elif args.action == 'status':
        if DEMO_DB_PATH.exists():
            print(f"[INFO] Demo database exists at {DEMO_DB_PATH} ({DEMO_DB_PATH.stat().st_size} bytes).")
        else:
            print("[INFO] Demo database is not initialized. Run 'python scripts/demo_mode.py setup'.")

if __name__ == '__main__':
    main()
