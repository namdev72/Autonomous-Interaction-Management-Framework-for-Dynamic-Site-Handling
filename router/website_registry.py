import json
import os
from typing import Dict, Any, Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "websites.json")

class WebsiteRegistry:
    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self.registry: Dict[str, Any] = {}
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.registry = json.load(f)
        else:
            self.registry = {}

    def get_website_config(self, website_key: str) -> Optional[Dict[str, Any]]:
        return self.registry.get(website_key.lower())

    def get_domain(self, website_key: str, region: Optional[str] = None) -> Optional[str]:
        config = self.get_website_config(website_key)
        if not config:
            return None
        
        domains = config.get("domains", {})
        if region and region in domains:
            return domains[region]
        
        default_region = config.get("default_region")
        if default_region and default_region in domains:
            return domains[default_region]
        
        # Fallback to first available if no default specified
        if domains:
            return list(domains.values())[0]
        return None

