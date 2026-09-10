import asyncio
import random
import httpx
from typing import Optional, Dict, Any
from playwright.async_api import Page
from app.services.browser_service import BrowserService
from app.services.captcha_service import CaptchaService
from app.services.temp_mail_service import TempMailService
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class DiscordService:
    def __init__(self, browser: BrowserService, captcha: CaptchaService, temp_mail: TempMailService):
        self.browser = browser
        self.captcha = captcha
        self.temp_mail = temp_mail
        self.reg_url = settings.DISCORD_REG_URL
        self.verify_url = settings.DISCORD_VERIFY_URL
        self.sitekey = settings.DISCORD_HCAPTCHA_SITEKEY

    async def create_account(self, proxy: Optional[str] = None) -> Dict[str, Any]:
        context = None
        try:
            context = await self.browser.create_context(proxy)
            page = await self.browser.create_page(context)

            await self.browser.inject_fingerprint_spoofs(page)

            temp_email_data = await self.temp_mail.create_email()
            if not temp_email_data:
                return {"success": False, "error": "Failed to create temp email"}

            email = temp_email_data["email"]
            username = self._generate_username()

            await page.goto(self.reg_url, wait_until="networkidle")
            await asyncio.sleep(random.uniform(1, 3))

            await self._fill_registration_form(page, email, username)
            await asyncio.sleep(random.uniform(1, 2))

            captcha_token = await self.captcha.solve_hcaptcha(self.sitekey, self.reg_url, proxy)
            if not captcha_token:
                return {"success": False, "error": "Failed to solve hCaptcha"}

            await self._inject_captcha_token(page, captcha_token)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            await self._submit_registration(page)
            await asyncio.sleep(random.uniform(2, 4))

            verify_link = await self.temp_mail.get_verification_link(email)
            if not verify_link:
                return {"success": False, "error": "Failed to get verification link"}

            await page.goto(verify_link, wait_until="networkidle")
            await asyncio.sleep(random.uniform(2, 4))

            token = await self._extract_token(page)
            if not token:
                return {"success": False, "error": "Failed to extract token"}

            return {
                "success": True,
                "email": email,
                "username": username,
                "token": token
            }

        except Exception as e:
            logger.error(f"Discord account creation failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if context:
                await context.close()

    def _generate_username(self) -> str:
        adjectives = ["swift", "silent", "bright", "calm", "dark", "fast", "gentle", "happy", "jolly", "kind"]
        nouns = ["fox", "wolf", "bear", "eagle", "shark", "tiger", "lion", "hawk", "owl", "deer"]
        num = random.randint(1000, 9999)
        return f"{random.choice(adjectives)}_{random.choice(nouns)}_{num}"

    async def _fill_registration_form(self, page: Page, email: str, username: str) -> None:
        await page.fill('input[name="email"]', email)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.fill('input[name="username"]', username)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.fill('input[name="password"]', "TempPass123!")
        await asyncio.sleep(random.uniform(0.3, 0.8))

    async def _inject_captcha_token(self, page: Page, token: str) -> None:
        await page.evaluate(f"""
            document.querySelector('[name="h-captcha-response"]').innerHTML = '{token}';
            document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{token}';
            if (window.hcaptcha) {{
                window.hcaptcha.getResponse = () => '{token}';
            }}
        """)

    async def _submit_registration(self, page: Page) -> None:
        await page.click('button[type="submit"]:has-text("Continue"), button[type="submit"]:has-text("Sign Up")')
        await page.wait_for_load_state("networkidle")

    async def _extract_token(self, page: Page) -> Optional[str]:
        try:
            token = await page.evaluate("""
                () => {
                    return localStorage.getItem('token') || 
                           sessionStorage.getItem('token') || 
                           document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
                }
            """)
            return token
        except Exception:
            return None