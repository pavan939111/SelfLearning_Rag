import json
import os
from utils.logger import get_logger

CONFIG_OVERRIDES_FILE = "config_overrides.json"
logger = get_logger(__name__)

def get_override(parameter: str, default):
    try:
        if not os.path.exists(CONFIG_OVERRIDES_FILE):
            return default
            
        with open(CONFIG_OVERRIDES_FILE, "r") as f:
            overrides = json.load(f)
            
        if parameter in overrides:
            val = overrides[parameter]
            # Convert type safely
            try:
                if isinstance(default, int):
                    return int(val)
                elif isinstance(default, float):
                    return float(val)
                elif isinstance(default, bool):
                    if isinstance(val, str):
                        return val.lower() == 'true'
                    return bool(val)
            except:
                pass
            return val
            
        return default
    except Exception as e:
        logger.warning(f"Failed to read config override for {parameter}: {e}")
        return default

def apply_override(parameter: str, value: str):
    try:
        overrides = {}
        if os.path.exists(CONFIG_OVERRIDES_FILE):
            try:
                with open(CONFIG_OVERRIDES_FILE, "r") as f:
                    overrides = json.load(f)
            except:
                overrides = {}
                
        overrides[parameter] = value
        
        with open(CONFIG_OVERRIDES_FILE, "w") as f:
            json.dump(overrides, f, indent=4)
            
        logger.info(f"Config override applied: {parameter} = {value}")
        return True
    except Exception as e:
        logger.error(f"Failed to apply config override {parameter}={value}: {e}")
        return False
