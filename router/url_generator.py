import urllib.parse
from typing import Optional, Dict, Any
from router.website_registry import WebsiteRegistry

class URLGenerator:
    def __init__(self, registry: WebsiteRegistry):
        self.registry = registry

    def generate_direct_url(self, website_key: str, intent: str, search_query: str, region: Optional[str] = None) -> Optional[str]:
        config = self.registry.get_website_config(website_key)
        if not config:
            return None

        if not config.get("search_supported", False) or intent not in ["search", "compare"]:
            return None

        domain = self.registry.get_domain(website_key, region)
        if not domain:
            return None

        routes = config.get("routes", {})
        search_route_template = routes.get("search")
        
        if not search_route_template:
            return None

        # Always URL-encode the extracted query safely
        encoded_query = urllib.parse.quote(search_query)
        
        # Construct the final URL safely
        route_path = search_route_template.replace("{query}", encoded_query)
        return f"{domain.rstrip('/')}{route_path}"

