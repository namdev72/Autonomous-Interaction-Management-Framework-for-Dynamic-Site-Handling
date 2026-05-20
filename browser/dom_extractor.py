from playwright.async_api import Page
from typing import List, Dict, Any
from loguru import logger
import json

class DOMExtractor:
    def __init__(self, page: Page):
        self.page = page

    async def extract_interactive_elements(self) -> List[Dict[str, Any]]:
        """
        Extracts interactive elements from the current DOM using JavaScript execution.
        Injects a unique 'data-playwright-id' into the elements for reliable targeting.
        """
        logger.info("Extracting interactive elements from the DOM...")
        
        js_script = """
        () => {
            function isVisible(el) {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            }

            function isChildOfInteractive(el) {
                let parent = el.parentElement;
                while (parent) {
                    const tag = parent.tagName.toLowerCase();
                    if (tag === 'a' || tag === 'button' || parent.getAttribute('role') === 'button' || parent.getAttribute('role') === 'link') {
                        return true;
                    }
                    parent = parent.parentElement;
                }
                return false;
            }

            function isInsideFooter(el) {
                let current = el;
                while (current) {
                    const tag = current.tagName.toLowerCase();
                    const id = (current.id || '').toLowerCase();
                    const className = (current.className || '').toLowerCase();
                    if (tag === 'footer' || id.includes('footer') || className.includes('footer') || id.includes('nav-footer') || className.includes('nav-footer')) {
                        return true;
                    }
                    current = current.parentElement;
                }
                return false;
            }

            const elements = document.querySelectorAll('h1, h2, h3, p, span.price_color, input, button, a, select, textarea, [role="button"], [role="link"], [tabindex]:not([tabindex="-1"])');
            const result = [];
            let counter = 0;
            
            elements.forEach((el) => {
                if (isVisible(el) && !el.disabled) {
                    const tag = el.tagName.toLowerCase();
                    
                    // Skip if inside footer unless it's a form input/button/select/textarea
                    if (isInsideFooter(el)) {
                        if (tag !== 'input' && tag !== 'button' && tag !== 'select' && tag !== 'textarea') {
                            return;
                        }
                    }
                    
                    // Skip if it's a child of another interactive element (unless it's an input/button/select/textarea)
                    if (isChildOfInteractive(el)) {
                        if (tag !== 'input' && tag !== 'button' && tag !== 'select' && tag !== 'textarea') {
                            return;
                        }
                    }
                    
                    // Inject ID into the DOM element itself so Playwright can find it later
                    const uniqueId = `pw-id-${counter}`;
                    el.setAttribute('data-playwright-id', uniqueId);
                    
                    const item = {
                        playwright_index: uniqueId,
                        tag: tag,
                        text: (el.innerText || el.value || '').trim().replace(/\\n/g, ' ').substring(0, 100), // Truncate slightly more to save tokens
                        placeholder: el.getAttribute('placeholder') || '',
                        id: el.id || '',
                        className: el.className || '',
                        aria_label: el.getAttribute('aria-label') || '',
                        role: el.getAttribute('role') || '',
                        href: el.getAttribute('href') || '',
                        type: el.getAttribute('type') || ''
                    };
                    
                    // Only keep elements that have some actionable or identifiable property
                    if (item.text || item.placeholder || item.aria_label || item.id || item.role || item.href) {
                         // Clean up empty fields
                         Object.keys(item).forEach(key => {
                             if (item[key] === '' || item[key] === null) {
                                 delete item[key];
                             }
                         });
                         result.push(item);
                         counter++;
                    } else {
                         // Remove the attribute if we didn't include it
                         el.removeAttribute('data-playwright-id');
                    }
                }
            });
            return result;
        }
        """
        
        # Retry mechanism to wait for DOM elements to render
        import asyncio
        for attempt in range(5):
            try:
                elements = await self.page.evaluate(js_script)
                if elements:
                    logger.info(f"Extracted {len(elements)} interactive elements (Attempt {attempt + 1}).")
                    return elements
            except Exception as e:
                logger.error(f"Failed to extract DOM elements: {e}")
            await asyncio.sleep(0.5)
            
        logger.warning("No interactive elements extracted from page.")
        return []
