"""Configuration validation module."""
import os
from dotenv import load_dotenv

def validate_config():
    """Validate that all required environment variables are set."""
    required_vars = [
        'ELASTICSEARCH_URL',
        'ELASTICSEARCH_USER',
        'ELASTICSEARCH_PASSWORD',
        'CHROMADB_HOST',
        'CHROMADB_PORT',
        'LLM_API_KEY',
        'LLM_MODEL',
        'LLM_API_BASE'
    ]
    
    # Load environment variables
    load_dotenv()
    
    # Check each required variable
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    # Report any missing variables
    if missing_vars:
        print("Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        return False
    
    return True 