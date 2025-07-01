# src/config.py

import configparser
import os

def load_config():
    """
    Loads and returns the main configuration object from config.ini.
    """
    config = configparser.ConfigParser()
    # Path is relative to this file's location in src/
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            "config.ini not found! Make sure it's in the project's root directory (C:\\champ)."
        )
        
    config.read(config_path)
    return config

# Load the config once and make it available for other modules to import
config = load_config()