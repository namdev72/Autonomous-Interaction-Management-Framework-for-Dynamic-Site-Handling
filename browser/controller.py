import asyncio
from urllib.parse import urlsplit
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from loguru import logger
from typing import Optional

class BrowserController:
    def __init__(self, headless: bool = False, allowed_hosts: Optional[set[str]] = None):
        # Visible by default so runs can be watched; callers that need no
        # window (comparison workers, --headless) pass headless=True.
        self.headless = headless
        self.allowed_hosts = allowed_hosts
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def launch_browser(self):
        logger.info("Launching browser...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--window-position=0,0"],
        )
        self.context = await self.browser.new_context(
            # Fixed rather than screen-sized: the DOM extractor reads only the
            # viewport, so a monitor-dependent size would change what the agent
            # sees, and what memory recalls, from one machine to the next.
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        await self.context.add_init_script("""
            document.addEventListener('click', function(e) {
                let link = e.target.closest('a');
                if (link && link.getAttribute('target') === '_blank') {
                    link.removeAttribute('target');
                }
            }, true);
        """)
        self.page = await self.context.new_page()
        logger.info("Browser launched and ready. Multi-tab behavior disabled.")

    async def open_website(self, url: str) -> bool:
        if not self.page:
            await self.launch_browser()
        
        logger.info(f"Navigating to {url}...")
        if not self.is_allowed_url(url):
            logger.error(f"Navigation blocked by site whitelist: {url}")
            return False
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            logger.info(f"Successfully loaded {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {e}")
            return False

    def is_allowed_url(self, url: str) -> bool:
        """Validate navigation targets when the caller supplies a whitelist."""
        if self.allowed_hosts is None:
            return True
        parsed = urlsplit(url)
        return parsed.scheme in {"http", "https"} and parsed.hostname in self.allowed_hosts

    async def wait_for_load(self):
        if self.page:
            try:
                # Wait briefly for network to settle, but don't fail if trackers keep it busy
                await self.page.wait_for_load_state("networkidle", timeout=2000)
            except Exception:
                pass

    async def close_browser(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed.")
