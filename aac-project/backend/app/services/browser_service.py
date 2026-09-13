import asyncio
import random
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright_stealth import Stealth
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class BrowserService:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.stealth = Stealth()
        self.user_agents = self._load_user_agents()
        self.viewport = {
            "width": settings.BROWSER_VIEWPORT_WIDTH,
            "height": settings.BROWSER_VIEWPORT_HEIGHT
        }

    def _load_user_agents(self) -> List[str]:
        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        ] * 5

    async def start(self, proxy: Optional[str] = None) -> None:
        self.playwright = await async_playwright().start()
        launch_options = {
            "headless": settings.BROWSER_HEADLESS,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        }
        if proxy:
            launch_options["proxy"] = {"server": proxy}

        self.browser = await self.playwright.chromium.launch(**launch_options)

    async def create_context(self, proxy: Optional[str] = None) -> BrowserContext:
        if not self.browser:
            await self.start(proxy)

        user_agent = random.choice(self.user_agents)
        locale = self._get_random_locale()
        timezone = self._get_timezone_for_locale(locale)

        context = await self.browser.new_context(
            viewport=self.viewport,
            user_agent=user_agent,
            locale=locale,
            timezone_id=timezone,
            ignore_https_errors=True,
            java_script_enabled=True,
            bypass_csp=True,
        )

        await self.stealth.apply_stealth_async(context)
        return context

    async def create_page(self, context: BrowserContext) -> Page:
        page = await context.new_page()
        page.set_default_timeout(settings.BROWSER_TIMEOUT)
        page.set_default_navigation_timeout(settings.BROWSER_TIMEOUT)
        return page

    def _get_random_locale(self) -> str:
        locales = [
            "en-US", "en-GB", "en-CA", "en-AU",
            "de-DE", "fr-FR", "es-ES", "it-IT",
            "pt-BR", "ru-RU", "ja-JP", "ko-KR",
            "zh-CN", "zh-TW", "id-ID", "vi-VN",
            "th-TH", "pl-PL", "nl-NL", "tr-TR",
        ]
        return random.choice(locales)

    def _get_timezone_for_locale(self, locale: str) -> str:
        timezone_map = {
            "en-US": "America/New_York",
            "en-GB": "Europe/London",
            "en-CA": "America/Toronto",
            "en-AU": "Australia/Sydney",
            "de-DE": "Europe/Berlin",
            "fr-FR": "Europe/Paris",
            "es-ES": "Europe/Madrid",
            "it-IT": "Europe/Rome",
            "pt-BR": "America/Sao_Paulo",
            "ru-RU": "Europe/Moscow",
            "ja-JP": "Asia/Tokyo",
            "ko-KR": "Asia/Seoul",
            "zh-CN": "Asia/Shanghai",
            "zh-TW": "Asia/Taipei",
            "id-ID": "Asia/Jakarta",
            "vi-VN": "Asia/Ho_Chi_Minh",
            "th-TH": "Asia/Bangkok",
            "pl-PL": "Europe/Warsaw",
            "nl-NL": "Europe/Amsterdam",
            "tr-TR": "Europe/Istanbul",
        }
        return timezone_map.get(locale, "UTC")

    async def inject_fingerprint_spoofs(self, page: Page) -> None:
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'permissions', {get: () => ({query: () => Promise.resolve({state: 'granted'})})});
        """)

        await page.add_init_script("""
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris Xe Graphics';
                return getParameter.call(this, parameter);
            };
        """)

        await page.add_init_script("""
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const ctx = this.getContext('2d');
                if (ctx) {
                    ctx.fillStyle = 'rgba(' + Math.random() * 255 + ',' + Math.random() * 255 + ',' + Math.random() * 255 + ',0.1)';
                    ctx.fillRect(0, 0, 1, 1);
                }
                return originalToDataURL.call(this, type);
            };
        """)

    async def close(self) -> None:
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Helper functions
def get_random_user_agent() -> str:
    """Get random user agent"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    return random.choice(user_agents)


async def setup_stealth_browser(playwright: Any, proxy_url: str, headless: bool = True):
    """Setup stealth browser with anti-detection"""
    launch_options = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ]
    }

    if proxy_url:
        launch_options["proxy"] = {"server": proxy_url}

    browser = await playwright.chromium.launch(**launch_options)

    context = await browser.new_context(
        viewport={"width": settings.BROWSER_VIEWPORT_WIDTH, "height": settings.BROWSER_VIEWPORT_HEIGHT},
        user_agent=get_random_user_agent(),
        locale="en-US",
        timezone_id="America/New_York",
        ignore_https_errors=True
    )

    stealth = Stealth()
    await stealth.apply_stealth_async(context)

    return context
