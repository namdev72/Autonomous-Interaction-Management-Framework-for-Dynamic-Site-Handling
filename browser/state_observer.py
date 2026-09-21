from playwright.async_api import Page
from loguru import logger
from models.goal_models import ObservedState

class StateObserver:
    """Collects cheap, structured evidence from the browser for goal verification."""
    def __init__(self, page: Page):
        self.page = page

    async def observe(self) -> ObservedState:
        try:
            url = self.page.url
            title = await self.page.title()
            
            # Extract static evidence using a lightweight script
            script = """
            () => {
                const headings = Array.from(document.querySelectorAll('h1, h2, h3')).map(e => e.innerText.trim()).filter(t => t);
                
                const selected = [];
                document.querySelectorAll('[aria-selected="true"], [aria-checked="true"], .selected, .active, input:checked, [data-selected="true"], .a-color-state').forEach(e => {
                    selected.push({
                        text: e.innerText.trim() || e.getAttribute('aria-label') || e.value || '',
                        tag: e.tagName.toLowerCase()
                    });
                });
                
                // Get the main visible text from the page
                // Instead of arbitrary text nodes, grab innerText and split by lines
                const rawText = document.body.innerText || "";
                const lines = rawText.split('\\n').map(l => l.trim()).filter(l => l.length > 2);
                
                // Keep the first 150 lines of meaningful text, which easily covers the main product info
                const visibleText = [...new Set(lines)].slice(0, 150);
                
                return {
                    headings: headings,
                    selected_states: selected,
                    visible_text: visibleText
                };
            }
            """
            data = await self.page.evaluate(script)
            
            return ObservedState(
                url=url,
                title=title,
                headings=data.get("headings", []),
                selected_states=data.get("selected_states", []),
                visible_text=data.get("visible_text", [])
            )
        except Exception as e:
            logger.error(f"Error observing state: {e}")
            return ObservedState(url=self.page.url, title="Error")
