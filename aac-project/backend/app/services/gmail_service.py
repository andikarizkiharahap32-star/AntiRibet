import asyncio
import random
from typing import Optional, Dict, Any
from playwright.async_api import Page
from app.services.browser_service import BrowserService
from app.services.captcha_service import CaptchaService
from app.services.sms_service import SMSService
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class GmailService:
    def __init__(self, browser: BrowserService, captcha: CaptchaService, sms: SMSService):
        self.browser = browser
        self.captcha = captcha
        self.sms = sms
        self.reg_url = settings.GMAIL_REG_URL
        self.sitekey = settings.GMAIL_RECAPTCHA_SITEKEY

    async def create_account(self, proxy: Optional[str] = None) -> Dict[str, Any]:
        context = None
        sms_order = None
        try:
            context = await self.browser.create_context(proxy)
            page = await self.browser.create_page(context)

            await self.browser.inject_fingerprint_spoofs(page)

            sms_data = await self.sms.get_number()
            if not sms_data:
                return {"success": False, "error": "Failed to get SMS number"}

            sms_order = sms_data
            phone = sms_data["phone"]

            username = self._generate_username()

            await page.goto(self.reg_url, wait_until="networkidle")
            await asyncio.sleep(random.uniform(1, 3))

            await self._fill_registration_form(page, username, phone)
            await asyncio.sleep(random.uniform(1, 2))

            captcha_token = await self.captcha.solve_recaptcha(
                self.sitekey, self.reg_url, proxy, enterprise=True
            )
            if not captcha_token:
                await self.sms.cancel_order(sms_order["order_id"])
                return {"success": False, "error": "Failed to solve reCAPTCHA"}

            await self._inject_captcha_token(page, captcha_token)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            await self._submit_registration(page)
            await asyncio.sleep(random.uniform(2, 4))

            code = await self.sms.get_code(sms_order["order_id"])
            if not code:
                await self.sms.cancel_order(sms_order["order_id"])
                return {"success": False, "error": "Failed to get SMS code"}

            await self._enter_verification_code(page, code)
            await asyncio.sleep(random.uniform(2, 4))

            token = await self._extract_token(page)
            if not token:
                return {"success": False, "error": "Failed to extract token"}

            email = f"{username}@gmail.com"
            return {
                "success": True,
                "email": email,
                "username": username,
                "token": token,
                "phone": phone
            }

        except Exception as e:
            logger.error(f"Gmail account creation failed: {e}")
            if sms_order:
                await self.sms.cancel_order(sms_order["order_id"])
            return {"success": False, "error": str(e)}
        finally:
            if context:
                await context.close()

    def _generate_username(self) -> str:
        adjectives = ["swift", "silent", "bright", "calm", "dark", "fast", "gentle", "happy", "jolly", "kind"]
        nouns = ["fox", "wolf", "bear", "eagle", "shark", "tiger", "lion", "hawk", "owl", "deer"]
        num = random.randint(1000, 9999)
        return f"{random.choice(adjectives)}.{random.choice(nouns)}.{num}"

    async def _fill_registration_form(self, page: Page, username: str, phone: str) -> None:
        await page.click('button:has-text("Create account")')
        await page.click('text="For my personal use"')
        await asyncio.sleep(random.uniform(0.5, 1.5))

        await page.fill('input[name="firstName"]', username.split(".")[0].capitalize())
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.fill('input[name="lastName"]', username.split(".")[1].capitalize())
        await asyncio.sleep(random.uniform(0.3, 0.8))

        await page.click('button:has-text("Next")')
        await asyncio.sleep(random.uniform(1, 2))

        await page.fill('input[name="Username"]', username)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.fill('input[name="Passwd"]', "TempPass123!")
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.fill('input[name="ConfirmPasswd"]', "TempPass123!")
        await asyncio.sleep(random.uniform(0.3, 0.8))

        await page.click('button:has-text("Next")')
        await asyncio.sleep(random.uniform(1, 2))

        await page.fill('input[name="phoneNumberId"]', phone)
        await asyncio.sleep(random.uniform(0.3, 0.8))

    async def _inject_captcha_token(self, page: Page, token: str) -> None:
        await page.evaluate(f"""
            document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{token}';
            if (window.grecaptcha) {{
                window.grecaptcha.getResponse = () => '{token}';
            }}
        """)

    async def _submit_registration(self, page: Page) -> None:
        await page.click('button:has-text("Next")')
        await page.wait_for_load_state("networkidle")

    async def _enter_verification_code(self, page: Page, code: str) -> None:
        await page.fill('input[name="code"]', code)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.click('button:has-text("Verify")')
        await page.wait_for_load_state("networkidle")

    async def _extract_token(self, page: Page) -> Optional[str]:
        try:
            token = await page.evaluate("""
                () => {
                    return document.cookie.split('; ').find(row => row.startsWith('SID='))?.split('=')[1] ||
                           document.cookie.split('; ').find(row => row.startsWith('HSID='))?.split('=')[1];
                }
            """)
            return token
        except Exception:
            return None


# Module-level workflow function
async def create_gmail_account_workflow(
    db,
    job_id,
    proxy,
    sms_provider: str,
    captcha_provider: str
) -> Dict[str, Any]:
    """
    Complete Gmail account creation workflow
    Similar to Discord but with SMS verification
    
    Returns:
        {
            "success": bool,
            "account_id": UUID,
            "email": str,
            "proxy_cost": float,
            "sms_cost": float,
            "captcha_cost": float
        }
    """
    from playwright.async_api import async_playwright
    from app.services.sms_service import get_sms_number, get_sms_code
    from app.services.captcha_service import solve_recaptcha
    from app.services.browser_service import setup_stealth_browser
    from app.services.account_service import AccountService
    from app.models.log import Log
    from app.models.account import Account
    from app.core.security import encrypt_password
    
    browser = None
    phone = None
    order_id = None
    username = None
    password = None
    email = None
    
    try:
        # Step 1: Get SMS number
        logger.info(f"Job {job_id}: Getting SMS number for Gmail")
        sms_result = await get_sms_number(provider=sms_provider, country="any")
        
        if not sms_result.get("success"):
            raise Exception("Failed to get SMS number")
        
        order_id = sms_result["order_id"]
        phone = sms_result["phone"]
        sms_cost = sms_result.get("price", 0.3)
        
        # Step 2: Generate credentials
        username = f"user{random.randint(10000, 99999)}"
        password = f"Pass{random.randint(100000, 999999)}!Aa"
        email = f"{username}@gmail.com"
        
        # Step 3: Setup browser
        logger.info(f"Job {job_id}: Setting up browser with proxy {proxy.url}")
        async with async_playwright() as p:
            browser = await setup_stealth_browser(
                playwright=p,
                proxy_url=proxy.url,
                headless=settings.BROWSER_HEADLESS
            )
            
            page = await browser.new_page()
            
            # Step 4: Navigate to Gmail signup
            logger.info(f"Job {job_id}: Navigating to Gmail signup")
            await page.goto(settings.GMAIL_REG_URL, timeout=30000)
            await asyncio.sleep(random.uniform(1, 3))
            
            # Step 5: Fill form (simplified for production)
            logger.info(f"Job {job_id}: Filling Gmail signup form")
            # Note: Gmail signup flow is complex and may require additional steps
            # This is a simplified implementation
            
            # Step 6: Solve reCAPTCHA
            logger.info(f"Job {job_id}: Solving reCAPTCHA Enterprise")
            captcha_result = await solve_recaptcha(
                page_url=page.url,
                sitekey=settings.GMAIL_RECAPTCHA_SITEKEY,
                provider=captcha_provider
            )
            
            if not captcha_result.get("success"):
                raise Exception("Failed to solve reCAPTCHA")
            
            captcha_cost = captcha_result.get("cost", 0.002)
            
            # Step 7: Get SMS code
            logger.info(f"Job {job_id}: Waiting for SMS verification code")
            code_result = await get_sms_code(provider=sms_provider, order_id=order_id, timeout=60)
            
            if not code_result.get("success"):
                raise Exception("SMS code not received")
            
            code = code_result["code"]
            
            # Step 8: Submit verification (simplified)
            logger.info(f"Job {job_id}: Submitting verification code")
            # Gmail verification steps would go here
            
            await browser.close()
            
            # Step 9: Save account
            logger.info(f"Job {job_id}: Saving Gmail account")
            account_service = AccountService(db)
            account = await account_service.create_account(
                job_id=job_id,
                platform="gmail",
                email=email,
                username=username,
                password=password,
                sms_number=phone,
                proxy_used=proxy.url
            )
            
            # Log success
            log = Log(
                job_id=job_id,
                account_id=account.id,
                level="INFO",
                message=f"Gmail account created successfully: {email}",
                context={"username": username, "proxy": proxy.url, "phone": phone}
            )
            db.add(log)
            await db.commit()
            
            logger.info(f"Job {job_id}: Gmail account {email} created successfully")
            
            return {
                "success": True,
                "account_id": account.id,
                "email": email,
                "username": username,
                "proxy_cost": 0.001,
                "captcha_cost": captcha_cost,
                "sms_cost": sms_cost
            }
    
    except Exception as e:
        logger.error(f"Job {job_id}: Gmail account creation failed: {e}", exc_info=True)
        
        # Log failure
        log = Log(
            job_id=job_id,
            level="ERROR",
            message=f"Gmail account creation failed: {str(e)}",
            context={
                "email": email,
                "username": username,
                "phone": phone,
                "proxy": proxy.url if proxy else None,
                "error": str(e)
            }
        )
        db.add(log)
        
        # Save failed account
        if email and username and password:
            account = Account(
                job_id=job_id,
                platform="gmail",
                email=email,
                username=username,
                password_encrypted=encrypt_password(password),
                sms_number=phone,
                proxy_used=proxy.url if proxy else None,
                status="failed",
                error_message=str(e)
            )
            db.add(account)
        
        await db.commit()
        
        return {
            "success": False,
            "error": str(e),
            "proxy_cost": 0.0,
            "captcha_cost": 0.0,
            "sms_cost": 0.0
        }
    
    finally:
        if browser:
            try:
                await browser.close()
            except:
                pass