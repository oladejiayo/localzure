"""
Service Bus Audit Logger

JSON-formatted audit logging for administrative operations on Service Bus entities.

Author: Ayodele Oladeji
Date: 2025-12-08
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path


class AuditLogger:
    """
    Audit logger for Service Bus administrative operations.
    
    Logs all create/delete/update operations on queues, topics, and subscriptions
    in structured JSON format for compliance and security monitoring.
    """
    
    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize audit logger.
        
        Args:
            log_file: Path to audit log file (default: servicebus_audit.json)
        """
        self.log_file = log_file or "servicebus_audit.json"
        
        # Configure logger
        self.logger = logging.getLogger("localzure.servicebus.audit")
        self.logger.setLevel(logging.INFO)
        
        # Create file handler if not already configured
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file)
            handler.setLevel(logging.INFO)
            
            # JSON formatter
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            
            self.logger.addHandler(handler)
    
    def _log_event(self, event_data: Dict[str, Any]) -> None:
        """
        Log an audit event.
        
        Args:
            event_data: Event data to log
        """
        # Add timestamp
        event_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        event_data["version"] = "1.0"
        
        # Log as JSON
        self.logger.info(json.dumps(event_data))
    
    def log_queue_created(
        self,
        queue_name: str,
        properties: Optional[Dict[str, Any]] = None,
        user: str = "system"
    ) -> None:
        """
        Log queue creation event.
        
        Args:
            queue_name: Name of the created queue
            properties: Queue properties
            user: User who created the queue
        """
        event = {
            "event_type": "queue_created",
            "entity_type": "queue",
            "entity_name": queue_name,
            "user": user,
            "properties": properties or {},
        }
        self._log_event(event)
    
    def log_queue_deleted(
        self,
        queue_name: str,
        user: str = "system"
    ) -> None:
        """
        Log queue deletion event.
        
        Args:
            queue_name: Name of the deleted queue
            user: User who deleted the queue
        """
        event = {
            "event_type": "queue_deleted",
            "entity_type": "queue",
            "entity_name": queue_name,
            "user": user,
        }
        self._log_event(event)
    
    def log_queue_updated(
        self,
        queue_name: str,
        properties: Dict[str, Any],
        user: str = "system"
    ) -> None:
        """
        Log queue update event.
        
        Args:
            queue_name: Name of the updated queue
            properties: Updated properties
            user: User who updated the queue
        """
        event = {
            "event_type": "queue_updated",
            "entity_type": "queue",
            "entity_name": queue_name,
            "user": user,
            "properties": properties,
        }
        self._log_event(event)
    
    def log_topic_created(
        self,
        topic_name: str,
        properties: Optional[Dict[str, Any]] = None,
        user: str = "system"
    ) -> None:
        """
        Log topic creation event.
        
        Args:
            topic_name: Name of the created topic
            properties: Topic properties
            user: User who created the topic
        """
        event = {
            "event_type": "topic_created",
            "entity_type": "topic",
            "entity_name": topic_name,
            "user": user,
            "properties": properties or {},
        }
        self._log_event(event)
    
    def log_topic_deleted(
        self,
        topic_name: str,
        user: str = "system"
    ) -> None:
        """
        Log topic deletion event.
        
        Args:
            topic_name: Name of the deleted topic
            user: User who deleted the topic
        """
        event = {
            "event_type": "topic_deleted",
            "entity_type": "topic",
            "entity_name": topic_name,
            "user": user,
        }
        self._log_event(event)
    
    def log_subscription_created(
        self,
        topic_name: str,
        subscription_name: str,
        properties: Optional[Dict[str, Any]] = None,
        user: str = "system"
    ) -> None:
        """
        Log subscription creation event.
        
        Args:
            topic_name: Parent topic name
            subscription_name: Name of the created subscription
            properties: Subscription properties
            user: User who created the subscription
        """
        event = {
            "event_type": "subscription_created",
            "entity_type": "subscription",
            "entity_name": f"{topic_name}/{subscription_name}",
            "topic_name": topic_name,
            "subscription_name": subscription_name,
            "user": user,
            "properties": properties or {},
        }
        self._log_event(event)
    
    def log_subscription_deleted(
        self,
        topic_name: str,
        subscription_name: str,
        user: str = "system"
    ) -> None:
        """
        Log subscription deletion event.
        
        Args:
            topic_name: Parent topic name
            subscription_name: Name of the deleted subscription
            user: User who deleted the subscription
        """
        event = {
            "event_type": "subscription_deleted",
            "entity_type": "subscription",
            "entity_name": f"{topic_name}/{subscription_name}",
            "topic_name": topic_name,
            "subscription_name": subscription_name,
            "user": user,
        }
        self._log_event(event)
    
    def log_rule_created(
        self,
        topic_name: str,
        subscription_name: str,
        rule_name: str,
        filter_expression: Optional[str] = None,
        user: str = "system"
    ) -> None:
        """
        Log rule creation event.
        
        Args:
            topic_name: Parent topic name
            subscription_name: Parent subscription name
            rule_name: Name of the created rule
            filter_expression: SQL filter expression
            user: User who created the rule
        """
        event = {
            "event_type": "rule_created",
            "entity_type": "rule",
            "entity_name": f"{topic_name}/{subscription_name}/{rule_name}",
            "topic_name": topic_name,
            "subscription_name": subscription_name,
            "rule_name": rule_name,
            "filter_expression": filter_expression,
            "user": user,
        }
        self._log_event(event)
    
    def log_rule_deleted(
        self,
        topic_name: str,
        subscription_name: str,
        rule_name: str,
        user: str = "system"
    ) -> None:
        """
        Log rule deletion event.
        
        Args:
            topic_name: Parent topic name
            subscription_name: Parent subscription name
            rule_name: Name of the deleted rule
            user: User who deleted the rule
        """
        event = {
            "event_type": "rule_deleted",
            "entity_type": "rule",
            "entity_name": f"{topic_name}/{subscription_name}/{rule_name}",
            "topic_name": topic_name,
            "subscription_name": subscription_name,
            "rule_name": rule_name,
            "user": user,
        }
        self._log_event(event)
    
    def log_security_violation(
        self,
        violation_type: str,
        entity_name: str,
        details: Dict[str, Any],
        user: str = "unknown"
    ) -> None:
        """
        Log security violation event.
        
        Args:
            violation_type: Type of violation (sql_injection, invalid_name, rate_limit, etc.)
            entity_name: Name of affected entity
            details: Additional violation details
            user: User who triggered the violation
        """
        event = {
            "event_type": "security_violation",
            "violation_type": violation_type,
            "entity_name": entity_name,
            "user": user,
            "severity": "high",
            **details,
        }
        self._log_event(event)
