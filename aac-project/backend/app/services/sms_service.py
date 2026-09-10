import asyncio
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class SMSService:
    def __init__(self):
        self.provider = settings.SMS_PROVIDER
        self.sims_key = settings.SIMS_API_KEY
        self.sims_url = settings.SIMS_API_URL
        self.smsactivate_key = settings.SMSACTIVATE_API_KEY
        self.smsactivate_url = settings.SMSACTIVATE_API_URL
        self.max_price = settings.SMS_MAX_PRICE
        self.timeout = settings.SMS_TIMEOUT

    async def get_number(self, country: str = "any", operator: str = "any") -> Optional[Dict[str, Any]]:
        if self.provider == "5sim":
            return await self._get_5sim_number(country, operator)
        elif self.provider == "smsactivate":
            return await self._get_smsactivate_number(country, operator)
        return None

    async def get_code(self, order_id: str) -> Optional[str]:
        if self.provider == "5sim":
            return await self._get_5sim_code(order_id)
        elif self.provider == "smsactivate":
            return await self._get_smsactivate_code(order_id)
        return None

    async def cancel_order(self, order_id: str) -> bool:
        if self.provider == "5sim":
            return await self._cancel_5sim_order(order_id)
        elif self.provider == "smsactivate":
            return await self._cancel_smsactivate_order(order_id)
        return False

    async def _get_5sim_number(self, country: str, operator: str) -> Optional[Dict[str, Any]]:
        try:
            headers = {"Authorization": f"Bearer {self.sims_key}"}
            async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
                response = await client.get(
                    f"{self.sims_url}/buy",
                    params={"country": country, "operator": operator, "product": "google"}
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("phone"):
                        return {
                            "order_id": str(data["id"]),
                            "phone": data["phone"],
                            "price": data.get("price", 0)
                        }
        except Exception as e:
            logger.error(f"5sim get number failed: {e}")
        return None

    async def _get_5sim_code(self, order_id: str) -> Optional[str]:
        try:
            headers = {"Authorization": f"Bearer {self.sims_key}"}
            async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < self.timeout:
                    await asyncio.sleep(5)
                    response = await client.get(f"{self.sims_url}/sms/{order_id}")
                    if response.status_code == 200:
                        data = response.json()
                        sms = data.get("sms", [])
                        if sms:
                            code = self._extract_code(sms[0].get("code", ""))
                            if code:
                                return code
        except Exception as e:
            logger.error(f"5sim get code failed: {e}")
        return None

    async def _cancel_5sim_order(self, order_id: str) -> bool:
        try:
            headers = {"Authorization": f"Bearer {self.sims_key}"}
            async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
                response = await client.get(f"{self.sims_url}/cancel/{order_id}")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"5sim cancel order failed: {e}")
        return False

    async def _get_smsactivate_number(self, country: str, operator: str) -> Optional[Dict[str, Any]]:
        try:
            country_map = {"any": "0", "us": "1", "ru": "0", "uk": "22"}
            country_code = country_map.get(country.lower(), "0")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.smsactivate_url,
                    params={
                        "api_key": self.smsactivate_key,
                        "action": "getNumber",
                        "service": "go",
                        "country": country_code,
                        "operator": operator
                    }
                )
                text = response.text
                if text.startswith("ACCESS_NUMBER:"):
                    parts = text.split(":")
                    return {
                        "order_id": parts[1],
                        "phone": parts[2],
                        "price": 0.0
                    }
        except Exception as e:
            logger.error(f"SMS-Activate get number failed: {e}")
        return None

    async def _get_smsactivate_code(self, order_id: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < self.timeout:
                    await asyncio.sleep(5)
                    response = await client.get(
                        self.smsactivate_url,
                        params={
                            "api_key": self.smsactivate_key,
                            "action": "getStatus",
                            "id": order_id
                        }
                    )
                    text = response.text
                    if text.startswith("STATUS_OK:"):
                        code = self._extract_code(text.split(":")[1])
                        return code
                    elif text == "STATUS_WAIT_CODE":
                        continue
                    elif text.startswith("STATUS_CANCEL"):
                        return None
        except Exception as e:
            logger.error(f"SMS-Activate get code failed: {e}")
        return None

    async def _cancel_smsactivate_order(self, order_id: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.smsactivate_url,
                    params={
                        "api_key": self.smsactivate_key,
                        "action": "setStatus",
                        "status": 8,
                        "id": order_id
                    }
                )
                return response.text == "ACCESS_CANCEL"
        except Exception as e:
            logger.error(f"SMS-Activate cancel order failed: {e}")
        return False

    def _extract_code(self, text: str) -> Optional[str]:
        import re
        match = re.search(r'\b(\d{6})\b', text)
        return match.group(1) if match else None


# Module-level helper functions
async def get_sms_number(provider: str = "5sim", country: str = "any") -> Dict[str, Any]:
    """
    Get SMS number for verification
    
    Returns:
        {
            "success": bool,
            "order_id": str,
            "phone": str,
            "price": float
        }
    """
    sms_service = SMSService()
    
    try:
        result = await sms_service.get_number(country=country)
        
        if result:
            return {
                "success": True,
                "order_id": result["order_id"],
                "phone": result["phone"],
                "price": result.get("price", 0.0)
            }
        else:
            return {"success": False, "error": "No number available"}
    
    except Exception as e:
        logger.error(f"Failed to get SMS number: {e}")
        return {"success": False, "error": str(e)}


async def get_sms_code(provider: str, order_id: str, timeout: int = 60) -> Dict[str, Any]:
    """
    Wait for and retrieve SMS code
    
    Returns:
        {
            "success": bool,
            "code": str
        }
    """
    sms_service = SMSService()
    
    try:
        code = await sms_service.get_code(order_id)
        
        if code:
            return {"success": True, "code": code}
        else:
            return {"success": False, "error": "Code not received"}
    
    except Exception as e:
        logger.error(f"Failed to get SMS code: {e}")
        return {"success": False, "error": str(e)}