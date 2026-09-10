"""
Captcha solving service
Integrates with 2Captcha and Anti-Captcha APIs
"""
import httpx
import asyncio
import logging
from typing import Optional, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


async def solve_hcaptcha(
    page_url: str,
    sitekey: str,
    provider: str = "2captcha"
) -> Dict[str, Any]:
    """
    Solve hCaptcha using external service
    
    Args:
        page_url: URL of the page with captcha
        sitekey: hCaptcha sitekey
        provider: "2captcha" or "anticaptcha"
    
    Returns:
        {
            "success": bool,
            "token": str,
            "cost": float
        }
    """
    try:
        if provider == "2captcha":
            return await _solve_hcaptcha_2captcha(page_url, sitekey)
        elif provider == "anticaptcha":
            return await _solve_hcaptcha_anticaptcha(page_url, sitekey)
        else:
            return {"success": False, "error": "Unknown provider"}
    
    except Exception as e:
        logger.error(f"Captcha solving failed: {e}")
        return {"success": False, "error": str(e)}


async def _solve_hcaptcha_2captcha(page_url: str, sitekey: str) -> Dict[str, Any]:
    """Solve hCaptcha using 2Captcha API"""
    api_key = settings.TWOCAPTCHA_API_KEY
    
    if not api_key:
        return {"success": False, "error": "2Captcha API key not configured"}
    
    async with httpx.AsyncClient(timeout=settings.CAPTCHA_TIMEOUT_HCAPTCHA) as client:
        # Step 1: Submit captcha task
        submit_response = await client.post(
            "http://2captcha.com/in.php",
            data={
                "key": api_key,
                "method": "hcaptcha",
                "sitekey": sitekey,
                "pageurl": page_url,
                "json": 1
            }
        )
        
        submit_data = submit_response.json()
        
        if submit_data.get("status") != 1:
            return {"success": False, "error": submit_data.get("request", "Unknown error")}
        
        task_id = submit_data["request"]
        
        # Step 2: Poll for result
        for _ in range(40):  # Max 40 attempts = 120 seconds
            await asyncio.sleep(3)
            
            result_response = await client.get(
                "http://2captcha.com/res.php",
                params={
                    "key": api_key,
                    "action": "get",
                    "id": task_id,
                    "json": 1
                }
            )
            
            result_data = result_response.json()
            
            if result_data.get("status") == 1:
                return {
                    "success": True,
                    "token": result_data["request"],
                    "cost": 0.001  # Estimated cost per solve
                }
            
            if result_data.get("request") != "CAPCHA_NOT_READY":
                return {"success": False, "error": result_data.get("request", "Unknown error")}
        
        return {"success": False, "error": "Timeout"}


async def _solve_hcaptcha_anticaptcha(page_url: str, sitekey: str) -> Dict[str, Any]:
    """Solve hCaptcha using Anti-Captcha API"""
    api_key = settings.ANTICAPTCHA_API_KEY
    
    if not api_key:
        return {"success": False, "error": "Anti-Captcha API key not configured"}
    
    async with httpx.AsyncClient(timeout=settings.CAPTCHA_TIMEOUT_HCAPTCHA) as client:
        # Step 1: Create task
        create_response = await client.post(
            "https://api.anti-captcha.com/createTask",
            json={
                "clientKey": api_key,
                "task": {
                    "type": "HCaptchaTaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": sitekey
                }
            }
        )
        
        create_data = create_response.json()
        
        if create_data.get("errorId") != 0:
            return {"success": False, "error": create_data.get("errorDescription", "Unknown error")}
        
        task_id = create_data["taskId"]
        
        # Step 2: Poll for result
        for _ in range(40):
            await asyncio.sleep(3)
            
            result_response = await client.post(
                "https://api.anti-captcha.com/getTaskResult",
                json={
                    "clientKey": api_key,
                    "taskId": task_id
                }
            )
            
            result_data = result_response.json()
            
            if result_data.get("status") == "ready":
                return {
                    "success": True,
                    "token": result_data["solution"]["gRecaptchaResponse"],
                    "cost": 0.001
                }
            
            if result_data.get("errorId") != 0:
                return {"success": False, "error": result_data.get("errorDescription", "Unknown error")}
        
        return {"success": False, "error": "Timeout"}


async def solve_recaptcha(
    page_url: str,
    sitekey: str,
    provider: str = "2captcha"
) -> Dict[str, Any]:
    """
    Solve reCAPTCHA v2/v3/Enterprise
    Similar to hCaptcha but with longer timeout
    """
    try:
        if provider == "2captcha":
            return await _solve_recaptcha_2captcha(page_url, sitekey)
        elif provider == "anticaptcha":
            return await _solve_recaptcha_anticaptcha(page_url, sitekey)
        else:
            return {"success": False, "error": "Unknown provider"}
    
    except Exception as e:
        logger.error(f"reCAPTCHA solving failed: {e}")
        return {"success": False, "error": str(e)}


async def _solve_recaptcha_2captcha(page_url: str, sitekey: str) -> Dict[str, Any]:
    """Solve reCAPTCHA using 2Captcha"""
    api_key = settings.TWOCAPTCHA_API_KEY
    
    async with httpx.AsyncClient(timeout=settings.CAPTCHA_TIMEOUT_RECAPTCHA) as client:
        submit_response = await client.post(
            "http://2captcha.com/in.php",
            data={
                "key": api_key,
                "method": "userrecaptcha",
                "googlekey": sitekey,
                "pageurl": page_url,
                "json": 1,
                "enterprise": 1  # Support Enterprise
            }
        )
        
        submit_data = submit_response.json()
        
        if submit_data.get("status") != 1:
            return {"success": False, "error": submit_data.get("request")}
        
        task_id = submit_data["request"]
        
        for _ in range(60):  # 180 seconds max
            await asyncio.sleep(3)
            
            result_response = await client.get(
                "http://2captcha.com/res.php",
                params={
                    "key": api_key,
                    "action": "get",
                    "id": task_id,
                    "json": 1
                }
            )
            
            result_data = result_response.json()
            
            if result_data.get("status") == 1:
                return {
                    "success": True,
                    "token": result_data["request"],
                    "cost": 0.002
                }
            
            if result_data.get("request") != "CAPCHA_NOT_READY":
                return {"success": False, "error": result_data.get("request")}
        
        return {"success": False, "error": "Timeout"}


async def _solve_recaptcha_anticaptcha(page_url: str, sitekey: str) -> Dict[str, Any]:
    """Solve reCAPTCHA using Anti-Captcha"""
    api_key = settings.ANTICAPTCHA_API_KEY
    
    async with httpx.AsyncClient(timeout=settings.CAPTCHA_TIMEOUT_RECAPTCHA) as client:
        create_response = await client.post(
            "https://api.anti-captcha.com/createTask",
            json={
                "clientKey": api_key,
                "task": {
                    "type": "RecaptchaV2EnterpriseTaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": sitekey
                }
            }
        )
        
        create_data = create_response.json()
        
        if create_data.get("errorId") != 0:
            return {"success": False, "error": create_data.get("errorDescription")}
        
        task_id = create_data["taskId"]
        
        for _ in range(60):
            await asyncio.sleep(3)
            
            result_response = await client.post(
                "https://api.anti-captcha.com/getTaskResult",
                json={
                    "clientKey": api_key,
                    "taskId": task_id
                }
            )
            
            result_data = result_response.json()
            
            if result_data.get("status") == "ready":
                return {
                    "success": True,
                    "token": result_data["solution"]["gRecaptchaResponse"],
                    "cost": 0.002
                }
            
            if result_data.get("errorId") != 0:
                return {"success": False, "error": result_data.get("errorDescription")}
        
        return {"success": False, "error": "Timeout"}
