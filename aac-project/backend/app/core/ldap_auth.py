import ldap3
from ldap3 import Server, Connection, ALL, STARTTLS, SUBTREE
from typing import Optional, Dict, Any, List
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class LDAPAuth:
    def __init__(self):
        self.server = Server(
            settings.LDAP_SERVER,
            get_info=ALL,
            use_ssl=False,
            connect_timeout=settings.LDAP_TIMEOUT
        )

    def _get_connection(self, user_dn: str = None, password: str = None) -> Connection:
        if user_dn and password:
            return Connection(
                self.server,
                user=user_dn,
                password=password,
                auto_bind=True,
                authentication=ldap3.SIMPLE
            )
        return Connection(
            self.server,
            user=settings.LDAP_BIND_DN,
            password=settings.LDAP_BIND_PASSWORD,
            auto_bind=True,
            authentication=ldap3.SIMPLE
        )

    async def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            
            if settings.LDAP_STARTTLS:
                conn.start_tls()

            user_filter = settings.LDAP_USER_SEARCH_FILTER.format(username=username)
            conn.search(
                settings.LDAP_USER_SEARCH_BASE,
                user_filter,
                SUBTREE,
                attributes=['dn', 'uid', 'cn', 'mail', 'memberOf']
            )

            if not conn.entries:
                logger.warning(f"LDAP user not found: {username}")
                return None

            user_entry = conn.entries[0]
            user_dn = str(user_entry.entry_dn)

            user_conn = self._get_connection(user_dn, password)
            if settings.LDAP_STARTTLS:
                user_conn.start_tls()

            if not user_conn.bind():
                logger.warning(f"LDAP bind failed for user: {username}")
                return None

            if not await self._check_group_membership(user_conn, user_dn):
                logger.warning(f"User {username} not in allowed group")
                return None

            return {
                "dn": user_dn,
                "username": str(user_entry.uid),
                "full_name": str(user_entry.cn) if user_entry.cn else username,
                "email": str(user_entry.mail) if user_entry.mail else "",
                "groups": [str(g) for g in user_entry.memberOf] if user_entry.memberOf else []
            }

        except Exception as e:
            logger.error(f"LDAP authentication error: {e}")
            return None

    async def _check_group_membership(self, conn: Connection, user_dn: str) -> bool:
        try:
            group_filter = f"(member={user_dn})"
            conn.search(
                settings.LDAP_GROUP_SEARCH_BASE,
                group_filter,
                SUBTREE,
                attributes=['cn', 'dn']
            )

            allowed_group_dn = settings.LDAP_ALLOWED_GROUP
            for entry in conn.entries:
                if str(entry.entry_dn).lower() == allowed_group_dn.lower():
                    return True

            conn.search(
                settings.LDAP_GROUP_SEARCH_BASE,
                f"(cn={allowed_group_dn.split(',')[0].split('=')[1]})",
                SUBTREE,
                attributes=['member']
            )

            if conn.entries:
                members = conn.entries[0].member.values if conn.entries[0].member else []
                return user_dn in members

            return False

        except Exception as e:
            logger.error(f"Group membership check error: {e}")
            return False

    async def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            if settings.LDAP_STARTTLS:
                conn.start_tls()

            user_filter = settings.LDAP_USER_SEARCH_FILTER.format(username=username)
            conn.search(
                settings.LDAP_USER_SEARCH_BASE,
                user_filter,
                SUBTREE,
                attributes=['dn', 'uid', 'cn', 'mail', 'memberOf']
            )

            if not conn.entries:
                return None

            user_entry = conn.entries[0]
            return {
                "dn": str(user_entry.entry_dn),
                "username": str(user_entry.uid),
                "full_name": str(user_entry.cn) if user_entry.cn else username,
                "email": str(user_entry.mail) if user_entry.mail else "",
                "groups": [str(g) for g in user_entry.memberOf] if user_entry.memberOf else []
            }

        except Exception as e:
            logger.error(f"LDAP get user info error: {e}")
            return None


ldap_auth = LDAPAuth()


async def verify_ldap_user(username: str, password: str) -> bool:
    """Verify user credentials against LDAP"""
    if not settings.LDAP_ENABLED:
        return False
    
    user_info = await ldap_auth.authenticate(username, password)
    return user_info is not None


async def get_ldap_user_groups(username: str) -> List[str]:
    """Get user groups from LDAP"""
    if not settings.LDAP_ENABLED:
        return []
    
    user_info = await ldap_auth.get_user_info(username)
    if user_info:
        return user_info.get("groups", [])
    return []