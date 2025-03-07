from pathlib import Path
import yaml
from typing import Dict, Any

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
DEFAULT_CONFIG = {
    "ollama_endpoint": "http://localhost:11434",
    "default_model": "qwen2.5",
}



def load_config() -> Dict[str, Any]:
    """Load the configuration from the config.yaml file."""
    with open(CONFIG_PATH, "r") as f:
        conf = yaml.safe_load(f)
        if not conf:
            update_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        return conf
def update_config(config: Dict[str, Any]) -> None:
    """Update the configuration in the config.yaml file."""
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f)