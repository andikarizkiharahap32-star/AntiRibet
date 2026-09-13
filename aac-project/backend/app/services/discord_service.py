import asyncio
import random
from typing import Optional, Dict, Any

from playwright.async_api import Page, async_playwright

from app.services.browser_service import setup_stealth_browser
from app.services.captcha_service import solve_hcaptcha
from app.services.temp_mail_service import create_temp_email, get_verification_link
from app.services.account_service import AccountService
from app.models.log import Log
from app.models.account import Account
from app.core.security import encrypt_password
from app.core.config import settings

import logging

logger = logging.getLogger(__name__)


class DiscordService:
    def __init__(self, browser, captcha, temp_mail):
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
                "token": token,
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
        await page.evaluate(
            f"""
            document.querySelector('[name="h-captcha-response"]').innerHTML = '{token}';
            document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{token}';
            if (window.hcaptcha) {{
                window.hcaptcha.getResponse = () => '{token}';
            }}
        """
        )

    async def _submit_registration(self, page: Page) -> None:
        await page.click('button[type="submit"]:has-text("Continue"), button[type="submit"]:has-text("Sign Up")')
        await page.wait_for_load_state("networkidle")

    async def _extract_token(self, page: Page) -> Optional[str]:
        try:
            token = await page.evaluate(
                """
                () => {
                    return localStorage.getItem('token') ||
                           sessionStorage.getItem('token') ||
                           document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
                }
            """
            )
            return token
        except Exception:
            return None


async def create_discord_account_workflow(
    db,
    job_id,
    proxy,
    captcha_provider: str,
) -> Dict[str, Any]:
    """Complete Discord account creation workflow used by Celery task."""
    browser = None
    token = None
    username = None
    password = None
    email = None

    try:
        logger.info(f"Job {job_id}: creating Discord account")

        # Step 1: temp email
        temp_result = await create_temp_email()
        if not temp_result.get("success"):
            raise Exception(temp_result.get("error", "Failed to create temp email"))

        email = temp_result["email"]
        temp_token = temp_result.get("token")

        # Step 2: credentials
        username = f"user{random.randint(10000, 99999)}"
        password = f"Pass{random.randint(100000, 999999)}!Aa"

        # Step 3: browser + registration
        async with async_playwright() as p:
            browser = await setup_stealth_browser(
                playwright=p,
                proxy_url=proxy.url,
                headless=settings.BROWSER_HEADLESS,
            )
            page = await browser.new_page()

            await page.goto(settings.DISCORD_REG_URL, timeout=settings.BROWSER_TIMEOUT)
            await asyncio.sleep(random.uniform(1, 2))

            await page.fill('input[name="email"]', email)
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)

            # Step 4: solve hcaptcha
            captcha_result = await solve_hcaptcha(
                page_url=page.url,
                sitekey=settings.DISCORD_HCAPTCHA_SITEKEY,
                provider=captcha_provider,
            )
            if not captcha_result.get("success"):
                raise Exception(captcha_result.get("error", "Failed to solve hCaptcha"))

            captcha_token = captcha_result["token"]
            await page.evaluate(
                f"""
                document.querySelector('[name="h-captcha-response"]').innerHTML = '{captcha_token}';
                document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{captcha_token}';
            """
            )

            await page.click('button[type="submit"]:has-text("Continue"), button[type="submit"]:has-text("Sign Up")')
            await asyncio.sleep(random.uniform(2, 4))

            # Step 5: verify email
            verify_result = await get_verification_link(
                email=email,
                token=temp_token,
                platform="discord",
                timeout=60,
            )
            if verify_result.get("success") and verify_result.get("link"):
                await page.goto(verify_result["link"], timeout=settings.BROWSER_TIMEOUT)
                await asyncio.sleep(random.uniform(1, 2))

            token = await page.evaluate(
                """
                () => {
                    return localStorage.getItem('token') ||
                           sessionStorage.getItem('token') ||
                           document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
                }
                """
            )

            await browser.close()
            browser = None

        # Step 6: persist
        account_service = AccountService(db)
        account = await account_service.create_account(
            job_id=job_id,
            platform="discord",
            email=email,
            username=username,
            password=password,
            token=token,
            proxy_used=proxy.url,
        )

        log = Log(
            job_id=job_id,
            account_id=account.id,
            level="INFO",
            message=f"Discord account created successfully: {email}",
            context={"username": username, "proxy": proxy.url},
        )
        db.add(log)
        await db.commit()

        return {
            "success": True,
            "account_id": account.id,
            "email": email,
            "username": username,
            "proxy_cost": 0.001,
            "captcha_cost": float(captcha_result.get("cost", 0.001)),
            "sms_cost": 0.0,
        }

    except Exception as e:
        logger.error(f"Job {job_id}: Discord account creation failed: {e}", exc_info=True)

        log = Log(
            job_id=job_id,
            level="ERROR",
            message=f"Discord account creation failed: {str(e)}",
            context={
                "email": email,
                "username": username,
                "proxy": proxy.url if proxy else None,
                "error": str(e),
            },
        )
        db.add(log)

        if email and username and password:
            account = Account(
                job_id=job_id,
                platform="discord",
                email=email,
                username=username,
                password_encrypted=encrypt_password(password),
                token=token,
                proxy_used=proxy.url if proxy else None,
                status="failed",
                error_message=str(e),
            )
            db.add(account)

        await db.commit()

        return {
            "success": False,
            "error": str(e),
            "proxy_cost": 0.0,
            "captcha_cost": 0.0,
            "sms_cost": 0.0,
        }

    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
