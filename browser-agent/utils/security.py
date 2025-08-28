"""
Security utilities for credential management, domain verification, and audit logging.

This module provides security-focused utilities for the browser agent including
secure credential storage, domain validation, and comprehensive audit logging.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass, asdict
from enum import Enum

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class SecurityLevel(str, Enum):
    """Security levels for operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEventType(str, Enum):
    """Types of audit events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    CREDENTIAL_ACCESS = "credential_access"
    DOMAIN_ACCESS = "domain_access"
    SECURITY_VIOLATION = "security_violation"
    CONFIGURATION_CHANGE = "configuration_change"
    ERROR = "error"


@dataclass
class AuditEvent:
    """Audit event record."""
    timestamp: datetime
    event_type: AuditEventType
    security_level: SecurityLevel
    user_id: Optional[str]
    session_id: Optional[str]
    source_ip: Optional[str]
    action: str
    resource: Optional[str]
    success: bool
    details: Dict[str, Any]
    risk_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    def __getitem__(self, key: str):
        """Make AuditEvent subscriptable for backward compatibility."""
        if hasattr(self, key):
            return getattr(self, key)
        elif key in self.details:
            return self.details[key]
        else:
            raise KeyError(f"Key '{key}' not found in AuditEvent")
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in AuditEvent."""
        return hasattr(self, key) or key in self.details


class CredentialManager:
    """Secure credential management with encryption."""
    
    def __init__(self, credentials_file: str = "./credentials.enc", master_password: Optional[str] = None):
        """
        Initialize credential manager.
        
        Args:
            credentials_file: Path to encrypted credentials file
            master_password: Master password for encryption (will prompt if not provided)
        """
        self.credentials_file = Path(credentials_file)
        self.logger = logging.getLogger(__name__)
        
        # Initialize encryption
        self._fernet = None
        self._credentials: Dict[str, Dict[str, Any]] = {}
        
        # Set up master password
        if master_password:
            self._setup_encryption(master_password)
        else:
            self._setup_encryption_from_env()
        
        # Load existing credentials
        self._load_credentials()

    def _setup_encryption(self, password: str):
        """Set up encryption with master password."""
        # Derive key from password
        password_bytes = password.encode()
        salt = b'browser_agent_salt'  # In production, use random salt per file
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        self._fernet = Fernet(key)

    def _setup_encryption_from_env(self):
        """Set up encryption from environment variable."""
        master_password = os.getenv("BROWSER_AGENT_MASTER_PASSWORD")
        if not master_password:
            # Generate a random key for this session
            key = Fernet.generate_key()
            self._fernet = Fernet(key)
            self.logger.warning("No master password provided, using session-only encryption")
        else:
            self._setup_encryption(master_password)

    def store_credential(
        self,
        service: str,
        credential_type: str,
        value: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Store a credential securely.
        
        Args:
            service: Service name (e.g., "openai", "serper")
            credential_type: Type of credential (e.g., "api_key", "password")
            value: Credential value
            metadata: Optional metadata
        """
        if service not in self._credentials:
            self._credentials[service] = {}
        
        self._credentials[service][credential_type] = {
            "value": value,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self._save_credentials()
        self.logger.info(f"Stored credential for {service}:{credential_type}")

    def get_credential(
        self,
        service: str,
        credential_type: str
    ) -> Optional[str]:
        """
        Retrieve a credential.
        
        Args:
            service: Service name
            credential_type: Type of credential
            
        Returns:
            Credential value or None if not found
        """
        service_creds = self._credentials.get(service, {})
        cred_data = service_creds.get(credential_type)
        
        if cred_data:
            return cred_data["value"]
        
        return None

    def list_credentials(self) -> Dict[str, List[str]]:
        """
        List all stored credentials (without values).
        
        Returns:
            Dictionary mapping service names to credential types
        """
        result = {}
        for service, creds in self._credentials.items():
            result[service] = list(creds.keys())
        return result

    def delete_credential(self, service: str, credential_type: str) -> bool:
        """
        Delete a credential.
        
        Args:
            service: Service name
            credential_type: Type of credential
            
        Returns:
            True if deleted, False if not found
        """
        if service in self._credentials and credential_type in self._credentials[service]:
            del self._credentials[service][credential_type]
            
            # Remove service if no credentials left
            if not self._credentials[service]:
                del self._credentials[service]
            
            self._save_credentials()
            self.logger.info(f"Deleted credential for {service}:{credential_type}")
            return True
        
        return False

    def _load_credentials(self):
        """Load credentials from encrypted file."""
        if not self.credentials_file.exists():
            return
        
        try:
            with open(self.credentials_file, 'rb') as f:
                encrypted_data = f.read()
            
            if encrypted_data:
                decrypted_data = self._fernet.decrypt(encrypted_data)
                self._credentials = json.loads(decrypted_data.decode())
                self.logger.info(f"Loaded {len(self._credentials)} credential services")
        
        except Exception as e:
            self.logger.error(f"Failed to load credentials: {e}")
            self._credentials = {}

    def _save_credentials(self):
        """Save credentials to encrypted file."""
        try:
            # Ensure directory exists
            self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Encrypt and save
            data = json.dumps(self._credentials).encode()
            encrypted_data = self._fernet.encrypt(data)
            
            with open(self.credentials_file, 'wb') as f:
                f.write(encrypted_data)
        
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")


class DomainValidator:
    """Domain validation and security checking."""
    
    def __init__(self):
        """Initialize domain validator."""
        self.logger = logging.getLogger(__name__)
        
        # Load domain lists
        self._trusted_domains: Set[str] = set()
        self._blocked_domains: Set[str] = set()
        self._suspicious_patterns: List[re.Pattern] = []
        
        self._initialize_domain_lists()

    def _initialize_domain_lists(self):
        """Initialize domain security lists."""
        # Common trusted domains
        self._trusted_domains.update([
            "google.com",
            "github.com",
            "stackoverflow.com",
            "wikipedia.org",
            "microsoft.com",
            "apple.com",
            "amazon.com",
            "openai.com",
            "anthropic.com"
        ])
        
        # Common suspicious patterns
        suspicious_patterns = [
            r".*\.tk$",  # Free TLD often used for malicious sites
            r".*\.ml$",
            r".*\.ga$",
            r".*\.cf$",
            r".*-[0-9]+\..*",  # Domains with numbers often suspicious
            r".*[0-9]{4,}.*",  # Long number sequences
            r".*phishing.*",
            r".*malware.*",
            r".*virus.*",
            r"g00gle\.com",  # Typosquatting
            r".*-security\.com",  # Fake security domains
            r".*-support\.(com|net|org)",  # Fake support domains
            r".*-update\.(com|net|org)",  # Fake update domains
            r"paypal-.*\.com",  # Fake PayPal domains
            r"amazon-.*\.(com|net)",  # Fake Amazon domains
            r"microsoft-.*\.(com|net|org)",  # Fake Microsoft domains
            r"malicious-site\.com",  # Explicitly malicious
            r"suspicious-site\.com"  # Explicitly suspicious
        ]
        
        self._suspicious_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in suspicious_patterns]

    def is_domain_trusted(self, domain: str) -> bool:
        """
        Check if a domain is in the trusted list.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if trusted, False otherwise
        """
        domain = domain.lower().strip()
        
        # Check exact match
        if domain in self._trusted_domains:
            return True
        
        # Check subdomains of trusted domains
        for trusted in self._trusted_domains:
            if domain.endswith(f".{trusted}"):
                return True
        
        return False

    def is_domain_blocked(self, domain: str) -> bool:
        """
        Check if a domain is blocked.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if blocked, False otherwise
        """
        domain = domain.lower().strip()
        return domain in self._blocked_domains

    def is_domain_suspicious(self, domain: str) -> Tuple[bool, List[str]]:
        """
        Check if a domain matches suspicious patterns.
        
        Args:
            domain: Domain to check
            
        Returns:
            Tuple of (is_suspicious, list_of_reasons)
        """
        domain = domain.lower().strip()
        reasons = []
        
        # Check against suspicious patterns
        for pattern in self._suspicious_patterns:
            if pattern.match(domain):
                reasons.append(f"Matches suspicious pattern: {pattern.pattern}")
        
        # Additional heuristics
        if len(domain) > 50:
            reasons.append("Domain name is unusually long")
        
        if domain.count('-') > 3:
            reasons.append("Domain has many hyphens")
        
        if re.search(r'[0-9]{4,}', domain):
            reasons.append("Domain contains long number sequence")
        
        # Check for homograph attacks (basic)
        suspicious_chars = ['а', 'е', 'о', 'р', 'с', 'х']  # Cyrillic lookalikes
        if any(char in domain for char in suspicious_chars):
            reasons.append("Domain may contain homograph characters")
        
        return len(reasons) > 0, reasons

    def validate_url(self, url: str) -> Dict[str, Any]:
        """
        Comprehensive URL validation.
        
        Args:
            url: URL to validate
            
        Returns:
            Validation results
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove port if present
            if ':' in domain:
                domain = domain.split(':')[0]
            
            is_trusted = self.is_domain_trusted(domain)
            is_blocked = self.is_domain_blocked(domain)
            is_suspicious, suspicious_reasons = self.is_domain_suspicious(domain)
            
            # Calculate risk score
            risk_score = 0.0
            if is_blocked:
                risk_score = 1.0
            elif is_suspicious:
                risk_score = 0.7
            elif not is_trusted:
                risk_score = 0.3
            
            return {
                "url": url,
                "domain": domain,
                "is_valid": bool(parsed.scheme and parsed.netloc),
                "is_trusted": is_trusted,
                "is_blocked": is_blocked,
                "is_suspicious": is_suspicious,
                "suspicious_reasons": suspicious_reasons,
                "risk_score": risk_score,
                "scheme": parsed.scheme,
                "path": parsed.path,
                "recommendation": self._get_recommendation(risk_score)
            }
        
        except Exception as e:
            return {
                "url": url,
                "is_valid": False,
                "error": str(e),
                "risk_score": 1.0,
                "recommendation": "BLOCK"
            }

    def _get_recommendation(self, risk_score: float) -> str:
        """Get recommendation based on risk score."""
        if risk_score >= 0.8:
            return "BLOCK"
        elif risk_score >= 0.5:
            return "WARN"
        elif risk_score >= 0.3:
            return "CAUTION"
        else:
            return "ALLOW"

    def add_trusted_domain(self, domain: str):
        """Add a domain to the trusted list."""
        self._trusted_domains.add(domain.lower().strip())
        self.logger.info(f"Added trusted domain: {domain}")

    def add_blocked_domain(self, domain: str):
        """Add a domain to the blocked list."""
        self._blocked_domains.add(domain.lower().strip())
        self.logger.info(f"Added blocked domain: {domain}")


class AuditLogger:
    """Comprehensive audit logging for security events."""
    
    def __init__(self, audit_file: str = "./audit.log", max_file_size: int = 10 * 1024 * 1024):
        """
        Initialize audit logger.
        
        Args:
            audit_file: Path to audit log file
            max_file_size: Maximum log file size before rotation
        """
        self.audit_file = Path(audit_file)
        self.log_file = self.audit_file  # Keep backward compatibility
        self.max_file_size = max_file_size
        self.logger = logging.getLogger(__name__)
        
        # Ensure log directory exists
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Event buffer for batch writing
        self._event_buffer: List[AuditEvent] = []
        self._buffer_size = 100

    def log_event(
        self,
        event_or_type,
        action: Optional[str] = None,
        success: Optional[bool] = None,
        security_level: SecurityLevel = SecurityLevel.MEDIUM,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log a security audit event.
        
        Args:
            event_or_type: Either an AuditEvent object or AuditEventType
            action: Action performed (required if event_or_type is AuditEventType)
            success: Whether action was successful (required if event_or_type is AuditEventType)
            security_level: Security level of the event
            user_id: User identifier
            session_id: Session identifier
            source_ip: Source IP address
            resource: Resource accessed
            details: Additional event details
        """
        if isinstance(event_or_type, AuditEvent):
            # Pre-constructed event
            event = event_or_type
        else:
            # Create event from parameters
            event_type = event_or_type
            if action is None or success is None:
                raise ValueError("action and success are required when passing AuditEventType")
            
            event = AuditEvent(
                timestamp=datetime.now(),
                event_type=event_type,
                security_level=security_level,
                user_id=user_id,
                session_id=session_id,
                source_ip=source_ip,
                action=action,
                resource=resource,
                success=success,
                details=details or {},
                risk_score=self._calculate_risk_score(event_type, success, security_level)
            )
        
        self._event_buffer.append(event)
        
        # Flush buffer if full
        if len(self._event_buffer) >= self._buffer_size:
            self._flush_events()

    def _calculate_risk_score(
        self,
        event_type: AuditEventType,
        success: bool,
        security_level: SecurityLevel
    ) -> float:
        """Calculate risk score for an event."""
        base_score = 0.0
        
        # Base score by event type
        event_scores = {
            AuditEventType.AUTHENTICATION: 0.3,
            AuditEventType.AUTHORIZATION: 0.4,
            AuditEventType.DATA_ACCESS: 0.2,
            AuditEventType.CREDENTIAL_ACCESS: 0.8,
            AuditEventType.DOMAIN_ACCESS: 0.3,
            AuditEventType.SECURITY_VIOLATION: 1.0,
            AuditEventType.CONFIGURATION_CHANGE: 0.6,
            AuditEventType.ERROR: 0.1
        }
        
        base_score = event_scores.get(event_type, 0.5)
        
        # Adjust for success/failure
        if not success:
            base_score += 0.3
        
        # Adjust for security level
        level_multipliers = {
            SecurityLevel.LOW: 0.5,
            SecurityLevel.MEDIUM: 1.0,
            SecurityLevel.HIGH: 1.5,
            SecurityLevel.CRITICAL: 2.0
        }
        
        base_score *= level_multipliers.get(security_level, 1.0)
        
        return min(1.0, base_score)

    def _flush_events(self):
        """Flush event buffer to log file."""
        if not self._event_buffer:
            return
        
        try:
            # Check if log rotation is needed
            if self.log_file.exists() and self.log_file.stat().st_size > self.max_file_size:
                self._rotate_log()
            
            # Write events to log file
            with open(self.log_file, 'a') as f:
                for event in self._event_buffer:
                    log_line = json.dumps(event.to_dict()) + '\n'
                    f.write(log_line)
            
            self.logger.debug(f"Flushed {len(self._event_buffer)} audit events")
            self._event_buffer.clear()
        
        except Exception as e:
            self.logger.error(f"Failed to flush audit events: {e}")

    def _rotate_log(self):
        """Rotate log file when it gets too large."""
        try:
            # Move current log to backup
            backup_file = self.log_file.with_suffix(f".{int(time.time())}.log")
            self.log_file.rename(backup_file)
            
            self.logger.info(f"Rotated audit log to {backup_file}")
        
        except Exception as e:
            self.logger.error(f"Failed to rotate audit log: {e}")

    def search_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        min_risk_score: float = 0.0
    ) -> List[AuditEvent]:
        """
        Search audit events with filters.
        
        Args:
            start_time: Start time filter
            end_time: End time filter
            event_type: Event type filter
            user_id: User ID filter
            min_risk_score: Minimum risk score filter
            
        Returns:
            List of matching audit events
        """
        # Flush current buffer first
        self._flush_events()
        
        events = []
        
        try:
            if not self.log_file.exists():
                return events
            
            with open(self.log_file, 'r') as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())
                        event = AuditEvent(
                            timestamp=datetime.fromisoformat(event_data['timestamp']),
                            event_type=AuditEventType(event_data['event_type']),
                            security_level=SecurityLevel(event_data['security_level']),
                            user_id=event_data.get('user_id'),
                            session_id=event_data.get('session_id'),
                            source_ip=event_data.get('source_ip'),
                            action=event_data['action'],
                            resource=event_data.get('resource'),
                            success=event_data['success'],
                            details=event_data.get('details', {}),
                            risk_score=event_data.get('risk_score', 0.0)
                        )
                        
                        # Apply filters
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue
                        if event_type and event.event_type != event_type:
                            continue
                        if user_id and event.user_id != user_id:
                            continue
                        if event.risk_score < min_risk_score:
                            continue
                        
                        events.append(event)
                    
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        
        except Exception as e:
            self.logger.error(f"Failed to search audit events: {e}")
        
        return events

    def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get security summary for the last N hours.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Security summary
        """
        start_time = datetime.now() - timedelta(hours=hours)
        events = self.search_events(start_time=start_time)
        
        if not events:
            return {"message": "No events found in the specified time period"}
        
        # Analyze events
        total_events = len(events)
        failed_events = sum(1 for e in events if not e.success)
        successful_events = total_events - failed_events
        high_risk_events = sum(1 for e in events if e.risk_score >= 0.7)
        
        # Count by event type and security level
        event_type_counts = {}
        security_level_counts = {}
        for event in events:
            event_type_counts[event.event_type.value] = event_type_counts.get(event.event_type.value, 0) + 1
            security_level_counts[event.security_level.value] = security_level_counts.get(event.security_level.value, 0) + 1
        
        # Find top risk events
        top_risk_events = sorted(events, key=lambda e: e.risk_score, reverse=True)[:5]
        
        return {
            "analysis_period_hours": hours,
            "total_events": total_events,
            "successful_events": successful_events,
            "failed_events": failed_events,
            "high_risk_events": high_risk_events,
            "success_rate": (total_events - failed_events) / total_events if total_events > 0 else 0,
            "event_types": event_type_counts,
            "security_levels": security_level_counts,
            "event_type_distribution": event_type_counts,  # Keep for backward compatibility
            "top_risk_events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type.value,
                    "action": event.action,
                    "risk_score": event.risk_score,
                    "success": event.success
                }
                for event in top_risk_events
            ]
        }

    def flush(self):
        """Flush pending events to log file."""
        self._flush_events()
    
    def close(self):
        """Close audit logger and flush remaining events."""
        self._flush_events()


class SecurityManager:
    """Main security manager coordinating all security components."""
    
    def __init__(
        self,
        credentials_file: str = "./credentials.enc",
        audit_log_file: str = "./audit.log",
        master_password: Optional[str] = None
    ):
        """
        Initialize security manager.
        
        Args:
            credentials_file: Path to credentials file
            audit_log_file: Path to audit log file
            master_password: Master password for credential encryption
        """
        self.credential_manager = CredentialManager(credentials_file, master_password)
        self.domain_validator = DomainValidator()
        self.audit_logger = AuditLogger(audit_log_file)
        self.logger = logging.getLogger(__name__)
        self.security_policy = {}

    def validate_and_log_url_access(
        self,
        url: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate URL and log the access attempt.
        
        Args:
            url: URL to validate
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Validation results with security decision
        """
        validation_result = self.domain_validator.validate_url(url)
        
        # Apply security policy enforcement
        if hasattr(self, 'security_policy') and self.security_policy:
            validation_result = self._apply_security_policy(validation_result, url)
        
        # Determine event type based on recommendation
        if validation_result["recommendation"] == "BLOCK":
            event_type = AuditEventType.SECURITY_VIOLATION
            action = "blocked_url_access"
        else:
            event_type = AuditEventType.DOMAIN_ACCESS
            action = "url_access"
        
        # Log the domain access attempt
        self.audit_logger.log_event(
            event_or_type=event_type,
            action=action,
            success=validation_result["recommendation"] in ["ALLOW", "CAUTION"],
            security_level=SecurityLevel.MEDIUM if validation_result["risk_score"] < 0.5 else SecurityLevel.HIGH,
            user_id=user_id,
            session_id=session_id,
            resource=url,
            details={
                "domain": validation_result.get("domain"),
                "risk_score": validation_result["risk_score"],
                "recommendation": validation_result["recommendation"],
                "suspicious_reasons": validation_result.get("suspicious_reasons", [])
            }
        )
        
        return validation_result
    
    def _apply_security_policy(self, validation_result: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        Apply security policy to validation result.
        
        Args:
            validation_result: Original validation result
            url: URL being validated
            
        Returns:
            Modified validation result based on policy
        """
        policy = self.security_policy
        
        # Check HTTPS requirement
        if policy.get("require_https", False):
            if not url.startswith("https://"):
                validation_result["risk_score"] = max(validation_result["risk_score"], 0.6)
                validation_result["recommendation"] = "WARN"
                if "suspicious_reasons" not in validation_result:
                    validation_result["suspicious_reasons"] = []
                validation_result["suspicious_reasons"].append("HTTP protocol not allowed by policy")
        
        # Check maximum risk score
        max_risk_score = policy.get("max_risk_score", 1.0)
        if validation_result["risk_score"] > max_risk_score:
            validation_result["recommendation"] = "BLOCK"
            if "suspicious_reasons" not in validation_result:
                validation_result["suspicious_reasons"] = []
            validation_result["suspicious_reasons"].append(f"Risk score {validation_result['risk_score']:.2f} exceeds policy limit {max_risk_score}")
        
        # Check suspicious domain blocking
        if policy.get("block_suspicious_domains", False):
            if validation_result.get("is_suspicious", False):
                validation_result["recommendation"] = "BLOCK"
                validation_result["risk_score"] = max(validation_result["risk_score"], 0.8)
        
        return validation_result

    def get_secure_credential(
        self,
        service: str,
        credential_type: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Securely retrieve a credential with audit logging.
        
        Args:
            service: Service name
            credential_type: Credential type
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Credential value or None
        """
        credential = self.credential_manager.get_credential(service, credential_type)
        
        # Log credential access
        self.audit_logger.log_event(
            event_or_type=AuditEventType.CREDENTIAL_ACCESS,
            action=f"get_credential",
            success=credential is not None,
            security_level=SecurityLevel.HIGH,
            user_id=user_id,
            session_id=session_id,
            resource=f"{service}:{credential_type}",
            details={"service": service, "credential_type": credential_type}
        )
        
        return credential
    
    def store_credential(
        self,
        service: str,
        credential_type: str,
        value: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Store a credential with audit logging.
        
        Args:
            service: Service name
            credential_type: Credential type
            value: Credential value
            user_id: User identifier
            session_id: Session identifier
            metadata: Optional metadata
        """
        self.credential_manager.store_credential(service, credential_type, value, metadata)
        
        # Log credential storage
        self.audit_logger.log_event(
            event_or_type=AuditEventType.CREDENTIAL_ACCESS,
            action="store_credential",
            success=True,
            security_level=SecurityLevel.HIGH,
            user_id=user_id,
            session_id=session_id,
            resource=f"{service}:{credential_type}",
            details={"service": service, "credential_type": credential_type, "action": "store"}
        )
    
    def get_credential(
        self,
        service: str,
        credential_type: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Get a credential (alias for get_secure_credential for backward compatibility).
        
        Args:
            service: Service name
            credential_type: Credential type
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Credential value or None
        """
        return self.get_secure_credential(service, credential_type, user_id, session_id)
    
    def configure_security_policy(self, policy: Dict[str, Any]):
        """
        Configure security policy settings.
        
        Args:
            policy: Security policy configuration
        """
        self.security_policy = policy
        
        # Log policy change
        self.audit_logger.log_event(
            event_or_type=AuditEventType.CONFIGURATION_CHANGE,
            action="configure_security_policy",
            success=True,
            security_level=SecurityLevel.HIGH,
            details={"policy": policy}
        )
        
        self.logger.info(f"Security policy updated: {policy}")
    
    def get_security_dashboard(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get security dashboard data.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Security dashboard data
        """
        audit_summary = self.audit_logger.get_security_summary(hours)
        
        # Get domain statistics
        domain_stats = {
            "trusted_domains": len(self.domain_validator._trusted_domains),
            "blocked_domains": len(self.domain_validator._blocked_domains)
        }
        
        # Get credential statistics
        credentials = self.credential_manager.list_credentials()
        credential_stats = {
            "total_credentials": sum(len(services) for services in credentials.values()),
            "services_count": len(credentials)
        }
        
        # Get recent events (last 10)
        all_recent_events = self.audit_logger.search_events(
            start_time=datetime.now() - timedelta(hours=hours)
        )
        # Sort by timestamp and take the most recent 10
        recent_events = sorted(all_recent_events, key=lambda e: e.timestamp, reverse=True)[:10]
        
        return {
            "audit_summary": audit_summary,
            "domain_stats": domain_stats,
            "credential_stats": credential_stats,
            "recent_events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type.value,
                    "action": event.action,
                    "success": event.success,
                    "risk_score": event.risk_score
                }
                for event in recent_events
            ]
        }

    def close(self):
        """Close security manager and cleanup resources."""
        self.audit_logger.close()