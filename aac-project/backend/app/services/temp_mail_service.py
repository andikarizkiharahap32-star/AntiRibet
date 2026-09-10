"""
Temporary email service
Integrates with mail.tm, 1secmail, and custom IMAP
"""
import httpx
import asyncio
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


async def create_temp_email() -> Dict[str, Any]:
    """
    Create temporary email address
    
    Returns:
        {
            "success": bool,
            "email": str,
            "token": str,  # For mail.tm authentication
            "password": str  # For IMAP or token
        }
    """
    provider = settings.TEMP_MAIL_PROVIDER
    
    try:
        if provider == "mailtm":
            return await _create_mailtm_email()
        elif provider == "1secmail":
            return await _create_1secmail_email()
        elif provider == "mailsac":
            return await _create_mailsac_email()
        else:
            return {"success": False, "error": "Unknown temp mail provider"}
    
    except Exception as e:
        logger.error(f"Failed to create temp email: {e}")
        return {"success": False, "error": str(e)}


async def get_verification_link(
    email: str,
    token: Optional[str] = None,
    platform: str = "discord",
    timeout: int = 60
) -> Dict[str, Any]:
    """
    Wait for and extract verification link from email
    
    Args:
        email: Email address to check
        token: Authentication token (for mail.tm)
        platform: "discord" or "gmail"
        timeout: Max seconds to wait
    
    Returns:
        {
            "success": bool,
            "link": str
        }
    """
    provider = settings.TEMP_MAIL_PROVIDER
    
    try:
        if provider == "mailtm":
            return await _get_mailtm_verification_link(email, token, platform, timeout)
        elif provider == "1secmail":
            return await _get_1secmail_verification_link(email, platform, timeout)
        elif provider == "mailsac":
            return await _get_mailsac_verification_link(email, platform, timeout)
        else:
            return {"success": False, "error": "Unknown provider"}
    
    except Exception as e:
        logger.error(f"Failed to get verification link: {e}")
        return {"success": False, "error": str(e)}


# Mail.tm implementation
async def _create_mailtm_email() -> Dict[str, Any]:
    """Create email using mail.tm API"""
    async with httpx.AsyncClient() as client:
        # Get available domains
        domains_response = await client.get(f"{settings.MAILTM_API_URL}/domains")
        domains = domains_response.json()
        
        if not domains or len(domains) == 0:
            return {"success": False, "error": "No domains available"}
        
        domain = domains[0]["domain"]
        
        # Generate random username
        import random
        import string
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{username}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        
        # Create account
        create_response = await client.post(
            f"{settings.MAILTM_API_URL}/accounts",
            json={
                "address": email,
                "password": password
            }
        )
        
        if create_response.status_code != 201:
            return {"success": False, "error": "Failed to create account"}
        
        # Get JWT token
        token_response = await client.post(
            f"{settings.MAILTM_API_URL}/token",
            json={
                "address": email,
                "password": password
            }
        )
        
        token_data = token_response.json()
        token = token_data.get("token")
        
        return {
            "success": True,
            "email": email,
            "token": token,
            "password": password
        }


async def _get_mailtm_verification_link(
    email: str,
    token: str,
    platform: str,
    timeout: int
) -> Dict[str, Any]:
    """Get verification link from mail.tm inbox"""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            # Get messages
            messages_response = await client.get(
                f"{settings.MAILTM_API_URL}/messages",
                headers=headers
            )
            
            if messages_response.status_code == 200:
                messages = messages_response.json()
                
                for msg in messages:
                    # Get full message
                    msg_response = await client.get(
                        f"{settings.MAILTM_API_URL}/messages/{msg['id']}",
                        headers=headers
                    )
                    
                    if msg_response.status_code == 200:
                        full_msg = msg_response.json()
                        html_content = full_msg.get("html", [])
                        text_content = full_msg.get("text", "")
                        
                        # Extract verification link
                        content = " ".join(html_content) + text_content
                        
                        if platform == "discord":
                            # Discord verification link pattern
                            match = re.search(r'https?://discord\.com/verify/[^\s"<>]+', content)
                            if match:
                                return {"success": True, "link": match.group(0)}
                        
                        elif platform == "gmail":
                            # Gmail verification link pattern
                            match = re.search(r'https?://accounts\.google\.com/[^\s"<>]+', content)
                            if match:
                                return {"success": True, "link": match.group(0)}
            
            await asyncio.sleep(5)
        
        return {"success": False, "error": "Verification email not received"}


# 1secmail implementation
async def _create_1secmail_email() -> Dict[str, Any]:
    """Create email using 1secmail API"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.ONESECMAIL_API_URL}",
            params={"action": "genRandomMailbox", "count": 1}
        )
        
        emails = response.json()
        
        if not emails or len(emails) == 0:
            return {"success": False, "error": "Failed to generate email"}
        
        email = emails[0]
        
        return {
            "success": True,
            "email": email,
            "token": None,
            "password": None
        }


async def _get_1secmail_verification_link(
    email: str,
    platform: str,
    timeout: int
) -> Dict[str, Any]:
    """Get verification link from 1secmail inbox"""
    username, domain = email.split("@")
    
    async with httpx.AsyncClient() as client:
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            # Get messages
            response = await client.get(
                f"{settings.ONESECMAIL_API_URL}",
                params={
                    "action": "getMessages",
                    "login": username,
                    "domain": domain
                }
            )
            
            messages = response.json()
            
            for msg in messages:
                # Get full message
                msg_response = await client.get(
                    f"{settings.ONESECMAIL_API_URL}",
                    params={
                        "action": "readMessage",
                        "login": username,
                        "domain": domain,
                        "id": msg["id"]
                    }
                )
                
                full_msg = msg_response.json()
                content = full_msg.get("body", "") + full_msg.get("textBody", "")
                
                # Extract verification link
                if platform == "discord":
                    match = re.search(r'https?://discord\.com/verify/[^\s"<>]+', content)
                    if match:
                        return {"success": True, "link": match.group(0)}
                
                elif platform == "gmail":
                    match = re.search(r'https?://accounts\.google\.com/[^\s"<>]+', content)
                    if match:
                        return {"success": True, "link": match.group(0)}
            
            await asyncio.sleep(5)
        
        return {"success": False, "error": "Verification email not received"}


# Mailsac implementation
async def _create_mailsac_email() -> Dict[str, Any]:
    """Create email using Mailsac API"""
    import random
    import string
    
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{username}@mailsac.com"
    
    return {
        "success": True,
        "email": email,
        "token": settings.MAILSAC_API_KEY,
        "password": None
    }


async def _get_mailsac_verification_link(
    email: str,
    platform: str,
    timeout: int
) -> Dict[str, Any]:
    """Get verification link from Mailsac inbox"""
    username = email.split("@")[0]
    
    async with httpx.AsyncClient() as client:
        headers = {"Mailsac-Key": settings.MAILSAC_API_KEY}
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            # Get messages
            response = await client.get(
                f"{settings.MAILSAC_API_URL}/addresses/{email}/messages",
                headers=headers
            )
            
            if response.status_code == 200:
                messages = response.json()
                
                for msg in messages:
                    # Get full message
                    msg_response = await client.get(
                        f"{settings.MAILSAC_API_URL}/text/{email}/{msg['_id']}",
                        headers=headers
                    )
                    
                    if msg_response.status_code == 200:
                        content = msg_response.text
                        
                        # Extract verification link
                        if platform == "discord":
                            match = re.search(r'https?://discord\.com/verify/[^\s"<>]+', content)
                            if match:
                                return {"success": True, "link": match.group(0)}
                        
                        elif platform == "gmail":
                            match = re.search(r'https?://accounts\.google\.com/[^\s"<>]+', content)
                            if match:
                                return {"success": True, "link": match.group(0)}
            
            await asyncio.sleep(5)
        
        return {"success": False, "error": "Verification email not received"}
