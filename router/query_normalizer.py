import re

class QueryNormalizer:
    @staticmethod
    def normalize_search_query(query: str, website: str) -> str:
        """
        Conservative query normalizer before URL generation.
        Removes conversational filler like "search for", "find the", etc.
        """
        text = query.strip()
        
        # Remove conversational prefixes
        text = re.sub(r"^(?:search\s+(?:for\s+)?|find\s+(?:the\s+)?|show\s+(?:me\s+)?|looking\s+(?:for\s+)?|open\s+(?:chrome\s+and\s+|browser\s+and\s+)?|go\s+to\s+)", "", text, flags=re.IGNORECASE)
        
        # Remove trailing on website
        website_pattern = re.compile(rf"\s+on\s+{re.escape(website)}(?:\s+india|\s+us)?$", re.IGNORECASE)
        text = website_pattern.sub("", text)
        
        # General punctuation cleanup but keep alpha-numeric intact
        text = text.strip(".!?")
        
        return text.strip()

