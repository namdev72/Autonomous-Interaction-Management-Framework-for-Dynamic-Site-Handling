import asyncio
import re
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
        # Off-site page loads stopped by the whitelist since the last check.
        self.blocked_navigations: list[str] = []

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
        if self.allowed_hosts is not None:
            await self._block_off_site_navigation()
        self.page = await self.context.new_page()
        await self.page.bring_to_front()
        logger.info("Browser launched and ready. Multi-tab behavior disabled.")

    async def _block_off_site_navigation(self):
        """
        is_allowed_url checks the URLs the agent opens itself, but a click, a
        redirect or a popup can still take the page to another site. Abort any
        top-level page load to a host that is not approved.

        Images, scripts and iframes (CDNs, embedded widgets) still load: only
        top-level page loads are checked. Requests to approved hosts never
        reach Python, which keeps the cost off normal page loads.
        """
        hosts = "|".join(re.escape(host) for host in sorted(self.allowed_hosts))
        off_site = re.compile(rf"^(?!https?://(?:{hosts})(?::\d+)?(?:[/?#]|$))")

        async def guard(route, request):
            if not request.is_navigation_request():
                await route.continue_()
                return
            try:
                top_level = request.frame.parent_frame is None
            except Exception:
                # A popup's first load starts before its frame exists.
                top_level = True
            if top_level:
                logger.warning(f"Blocked navigation off the approved sites: {request.url}")
                self.blocked_navigations.append(request.url)
                # 204 cancels the navigation and leaves the current page as it
                # is; aborting would replace it with the browser's error page.
                await route.fulfill(status=204)
            else:
                await route.continue_()

        await self.context.route(off_site, guard)

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
