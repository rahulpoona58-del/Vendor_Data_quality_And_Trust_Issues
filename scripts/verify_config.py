import sys
from pathlib import Path

# Add project root directory to python path to resolve src imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import get_config
from src.infrastructure.logging.logger import setup_logging
import logging

def main():
    print("=== Verification Script Running ===")
    config = get_config()
    print(f"Flask Environment: {config.__class__.__name__}")
    print(f"Database URL:      {config.SQLALCHEMY_DATABASE_URI}")
    print(f"CSV File Path:     {config.CSV_DATA_PATH}")
    print(f"Log Level setting: {config.LOG_LEVEL}")
    
    # Initialize logging
    setup_logging(config)
    
    # Send some test log entries
    logging.info("Configuration loaded successfully!")
    logging.debug("This is a debug log verifying logger output.")
    logging.warning("This is a warning log message.")
    
    print("=== Verification Script Completed ===")

if __name__ == '__main__':
    main()
