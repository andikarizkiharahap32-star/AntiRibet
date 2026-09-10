"""
Proxy management service
Handles proxy rotation, health checking, and performance tracking
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, List
import httpx
import logging
import asyncio
from datetime import datetime, timedelta

from app.models.proxy import Proxy
from app.models.proxy_usage import ProxyUsage
from app.core.config import settings

logger = logging.getLogger(__name__)


class ProxyService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_next_proxy(self, provider: Optional[str] = None) -> Optional[Proxy]:
        """
        Get next available proxy from pool
        - Filters by provider if specified
        - Returns active proxies only
        - Random selection
        """
        query = select(Proxy).where(Proxy.status == "active")
        
        if provider:
            query = query.where(Proxy.provider == provider)
        
        # Prefer residential proxies
        query = query.order_by(Proxy.type.desc(), Proxy.success_count.desc())
        
        result = await self.db.execute(query.limit(10))
        proxies = list(result.scalars().all())
        
        if not proxies:
            logger.warning(f"No active proxies available for provider {provider}")
            return None
        
        # Random selection from top 10
        import random
        proxy = random.choice(proxies)
        
        # Update last_used
        proxy.last_used = datetime.utcnow()
        await self.db.commit()
        
        return proxy
    
    async def record_proxy_success(self, proxy_id: int, response_time_ms: int = None):
        """Record successful proxy usage"""
        result = await self.db.execute(
            select(Proxy).where(Proxy.id == proxy_id)
        )
        proxy = result.scalar_one_or_none()
        
        if proxy:
            proxy.success_count += 1
            if response_time_ms:
                proxy.response_time_ms = response_time_ms
            proxy.last_used = datetime.utcnow()
            await self.db.commit()
    
    async def record_proxy_failure(self, proxy_id: int):
        """Record failed proxy usage"""
        result = await self.db.execute(
            select(Proxy).where(Proxy.id == proxy_id)
        )
        proxy = result.scalar_one_or_none()
        
        if proxy:
            proxy.fail_count += 1
            
            # Mark as dead if too many failures
            if proxy.fail_count > 5:
                proxy.status = "dead"
                logger.warning(f"Proxy {proxy_id} marked as dead after {proxy.fail_count} failures")
            
            await self.db.commit()
    
    async def health_check_proxy(self, proxy: Proxy) -> bool:
        """
        Check if proxy is healthy
        - Makes request to httpbin.org/ip
        - Timeout: 10 seconds
        - Returns True if successful
        """
        try:
            async with httpx.AsyncClient(
                proxies=proxy.url,
                timeout=10.0
            ) as client:
                start_time = datetime.utcnow()
                response = await client.get("http://httpbin.org/ip")
                end_time = datetime.utcnow()
                
                if response.status_code == 200:
                    response_time = int((end_time - start_time).total_seconds() * 1000)
                    proxy.status = "active"
                    proxy.response_time_ms = response_time
                    proxy.last_checked = datetime.utcnow()
                    await self.db.commit()
                    return True
                else:
                    proxy.status = "inactive"
                    proxy.last_checked = datetime.utcnow()
                    await self.db.commit()
                    return False
        
        except Exception as e:
            logger.error(f"Proxy health check failed for {proxy.id}: {e}")
            proxy.status = "inactive"
            proxy.last_checked = datetime.utcnow()
            await self.db.commit()
            return False
    
    async def health_check_all_proxies(self) -> int:
        """
        Check health of all proxies
        Returns count of checked proxies
        """
        result = await self.db.execute(
            select(Proxy).where(Proxy.status.in_(["active", "inactive"]))
        )
        proxies = result.scalars().all()
        
        tasks = [self.health_check_proxy(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        checked_count = sum(1 for r in results if isinstance(r, bool))
        return checked_count
    
    async def add_proxy(
        self,
        url: str,
        provider: str,
        type: str = "residential"
    ) -> Proxy:
        """Add new proxy to pool"""
        proxy = Proxy(
            url=url,
            provider=provider,
            type=type,
            status="active"
        )
        
        self.db.add(proxy)
        await self.db.commit()
        await self.db.refresh(proxy)
        
        logger.info(f"Added proxy {proxy.id} from {provider}")
        return proxy
    
    async def get_proxy_stats(self, provider: Optional[str] = None) -> dict:
        """Get proxy statistics"""
        query = select(Proxy)
        if provider:
            query = query.where(Proxy.provider == provider)
        
        result = await self.db.execute(query)
        proxies = result.scalars().all()
        
        total = len(proxies)
        active = sum(1 for p in proxies if p.status == "active")
        dead = sum(1 for p in proxies if p.status == "dead")
        
        success_rates = [
            p.success_count / (p.success_count + p.fail_count)
            if (p.success_count + p.fail_count) > 0 else 0
            for p in proxies
        ]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0
        
        return {
            "total": total,
            "active": active,
            "dead": dead,
            "average_success_rate": round(avg_success_rate, 4)
        }


async def init_proxies_from_provider(db: AsyncSession, provider: str):
    """
    Initialize proxies from external provider
    - Bright Data or Smartproxy
    """
    proxy_service = ProxyService(db)
    
    if provider == "brightdata":
        # Bright Data proxy format
        proxy_url = f"http://{settings.BRIGHTDATA_USERNAME}:{settings.BRIGHTDATA_PASSWORD}@brd.superproxy.io:22225"
        await proxy_service.add_proxy(proxy_url, "brightdata", "residential")
        logger.info("Initialized Bright Data proxy")
    
    elif provider == "smartproxy":
        # Smartproxy format
        proxy_url = f"http://{settings.SMARTPROXY_USERNAME}:{settings.SMARTPROXY_PASSWORD}@gate.smartproxy.com:7000"
        await proxy_service.add_proxy(proxy_url, "smartproxy", "residential")
        logger.info("Initialized Smartproxy proxy")
