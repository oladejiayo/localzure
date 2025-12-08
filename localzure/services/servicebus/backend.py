"""
Service Bus Backend.

Backend implementation for Azure Service Bus queue management and message operations.
Provides in-memory storage and operations for queues, topics, subscriptions, and messages
with Azure-compatible behavior.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from .constants import (
    MAX_QUEUES,
    MAX_TOPICS,
    DEFAULT_MESSAGE_TTL,
    DEFAULT_LOCK_DURATION,
    MAX_SUBSCRIPTIONS_PER_TOPIC,
)
from .filter_evaluator import SqlFilterEvaluator
from .logging_utils import StructuredLogger, track_operation_time
from .validation import (
    EntityNameValidator,
    MessageValidator,
    SqlFilterSanitizer,
    LockTokenValidator,
    SessionIdValidator,
)
from .rate_limiter import ServiceBusRateLimiter
from .audit_logger import AuditLogger
from .metrics import get_metrics
from .models import (
    QueueDescription,
    QueueProperties,
    QueueRuntimeInfo,
    ServiceBusMessage,
    SendMessageRequest,
    ReceiveMode,
    TopicDescription,
    TopicProperties,
    TopicRuntimeInfo,
    SubscriptionDescription,
    SubscriptionProperties,
    SubscriptionRuntimeInfo,
    SubscriptionFilter,
    FilterType,
    RuleDescription,
)
from .exceptions import (
    ServiceBusError,
    QueueAlreadyExistsError,
    QueueNotFoundError,
    InvalidQueueNameError,
    QuotaExceededError,
    MessageNotFoundError,
    MessageLockLostError,
    MessageSizeExceededError,
    TopicAlreadyExistsError,
    TopicNotFoundError,
    SubscriptionAlreadyExistsError,
    SubscriptionNotFoundError,
    RuleAlreadyExistsError,
    RuleNotFoundError,
    SessionLockLostError,
    SessionNotFoundError,
    InvalidOperationError,
    DeadLetterReason,
)


class ServiceBusBackend:
    """
    Backend for Service Bus operations.
    
    Manages Service Bus entities (queues, topics, subscriptions) in memory,
    providing Azure-compatible CRUD operations and message handling.
    
    Attributes:
        _queues: Dictionary mapping queue names to QueueDescription objects
        _messages: Dictionary mapping queue names to message lists
        _topics: Dictionary mapping topic names to TopicDescription objects  
        _subscriptions: Dictionary mapping (topic, subscription) to descriptions
        _lock: Asyncio lock for thread-safe operations
        _logger: Structured logger instance
        _filter_evaluator: SQL filter evaluator for subscription filters
    """
    
    def __init__(self):
        """Initialize the Service Bus backend with empty storage."""
        # Queue storage
        self._queues: Dict[str, QueueDescription] = {}
        self._messages: Dict[str, List[ServiceBusMessage]] = {}
        self._dead_letter_messages: Dict[str, List[ServiceBusMessage]] = {}
        self._locked_messages: Dict[
            str,
            Dict[str, Tuple[ServiceBusMessage, datetime]]
        ] = {}
        self._sequence_counters: Dict[str, int] = {}
        
        # Topic and subscription storage
        self._topics: Dict[str, TopicDescription] = {}
        self._subscriptions: Dict[
            Tuple[str, str],
            SubscriptionDescription
        ] = {}
        self._subscription_messages: Dict[
            Tuple[str, str],
            List[ServiceBusMessage]
        ] = {}
        self._subscription_locked: Dict[
            Tuple[str, str],
            Dict[str, Tuple[ServiceBusMessage, datetime]]
        ] = {}
        self._subscription_dead_letter: Dict[
            Tuple[str, str],
            List[ServiceBusMessage]
        ] = {}
        
        self._lock = asyncio.Lock()
        self._max_queues = MAX_QUEUES
        self._max_topics = MAX_TOPICS
        
        # Initialize components
        self._logger = StructuredLogger('localzure.services.servicebus.backend')
        self._filter_evaluator = SqlFilterEvaluator()
        
        # Initialize validators and rate limiter
        self._entity_validator = EntityNameValidator()
        self._message_validator = MessageValidator()
        self._sql_sanitizer = SqlFilterSanitizer()
        self._lock_token_validator = LockTokenValidator()
        self._session_validator = SessionIdValidator()
        self._rate_limiter = ServiceBusRateLimiter()
        self._audit_logger = AuditLogger()
        self._metrics = get_metrics()
        
        # Start background metrics collection
        self._metrics_task = None
        self._metrics_running = False
    
    async def start_metrics_collection(self):
        """Start background metrics collection task."""
        if not self._metrics_running:
            self._metrics_running = True
            self._metrics_task = asyncio.create_task(self._collect_metrics_loop())
    
    async def stop_metrics_collection(self):
        """Stop background metrics collection task."""
        self._metrics_running = False
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass
    
    async def _collect_metrics_loop(self):
        """Background task to collect gauge metrics every 10 seconds."""
        while self._metrics_running:
            try:
                await asyncio.sleep(10)
                await self._collect_gauge_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.log_error(
                    operation="metrics_collection",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
    
    async def _collect_gauge_metrics(self):
        """Collect and update all gauge metrics."""
        async with self._lock:
            # Update queue metrics
            for queue_name, messages in self._messages.items():
                active_count = len([m for m in messages if not m.scheduled_enqueue_time_utc or m.scheduled_enqueue_time_utc <= datetime.now(timezone.utc)])
                scheduled_count = len([m for m in messages if m.scheduled_enqueue_time_utc and m.scheduled_enqueue_time_utc > datetime.now(timezone.utc)])
                deadletter_count = len(self._dead_letter_messages.get(queue_name, []))
                lock_count = len(self._locked_messages.get(queue_name, {}))
                
                self._metrics.update_active_messages('queue', queue_name, active_count)
                self._metrics.update_scheduled_messages('queue', queue_name, scheduled_count)
                self._metrics.update_deadletter_messages('queue', queue_name, deadletter_count)
                self._metrics.update_active_locks('queue', queue_name, lock_count)
            
            # Update topic/subscription metrics
            for (topic_name, sub_name), messages in self._subscription_messages.items():
                active_count = len([m for m in messages if not m.scheduled_enqueue_time_utc or m.scheduled_enqueue_time_utc <= datetime.now(timezone.utc)])
                scheduled_count = len([m for m in messages if m.scheduled_enqueue_time_utc and m.scheduled_enqueue_time_utc > datetime.now(timezone.utc)])
                deadletter_count = len(self._subscription_dead_letter.get((topic_name, sub_name), []))
                lock_count = len(self._subscription_locked.get((topic_name, sub_name), {}))
                
                entity_name = f"{topic_name}/{sub_name}"
                self._metrics.update_active_messages('subscription', entity_name, active_count)
                self._metrics.update_scheduled_messages('subscription', entity_name, scheduled_count)
                self._metrics.update_deadletter_messages('subscription', entity_name, deadletter_count)
                self._metrics.update_active_locks('subscription', entity_name, lock_count)
            
            # Update entity counts
            self._metrics.update_entity_count('queue', len(self._queues))
            self._metrics.update_entity_count('topic', len(self._topics))
            self._metrics.update_entity_count('subscription', len(self._subscriptions))
    
    async def create_queue(
        self,
        name: str,
        properties: Optional[QueueProperties] = None,
    ) -> QueueDescription:
        """
        Create a new Service Bus queue.
        
        Args:
            name: Queue name
            properties: Optional queue properties
            
        Returns:
            Created QueueDescription
            
        Raises:
            QueueAlreadyExistsError: Queue already exists
            QuotaExceededError: Maximum queue count exceeded
            InvalidQueueNameError: Queue name is invalid
        """
        # Validate queue name
        self._entity_validator.validate_queue_name(name)
        
        async with self._lock:
            # Check quota
            if len(self._queues) >= self._max_queues:
                raise QuotaExceededError("queue_count", len(self._queues), self._max_queues)
            
            # Check if queue exists
            if name in self._queues:
                raise QueueAlreadyExistsError(f"Queue '{name}' already exists")
            
            # Create queue
            try:
                queue = QueueDescription(
                    name=name,
                    properties=properties or QueueProperties(),
                    runtime_info=QueueRuntimeInfo(),
                )
            except ValueError as e:
                self._logger.log_error(
                    operation="queue_create",
                    error_type="InvalidQueueNameError",
                    error_message=str(e),
                    entity_type="queue",
                    entity_name=name
                )
                raise InvalidQueueNameError(queue_name=name, reason=str(e))
            
            # Store queue and initialize message storage
            self._queues[name] = queue
            self._messages[name] = []
            
            # Audit log
            self._audit_logger.log_queue_created(
                queue_name=name,
                properties={
                    "lock_duration": properties.lock_duration if properties else 60,
                    "max_delivery_count": properties.max_delivery_count if properties else 10
                }
            )
            
            self._logger.log_operation(
                operation="queue_created",
                entity_type="queue",
                entity_name=name,
                lock_duration=properties.lock_duration if properties else 60,
                max_delivery_count=properties.max_delivery_count if properties else 10
            )
            
            return queue
    
    async def list_queues(
        self,
        skip: int = 0,
        top: int = 100,
    ) -> List[QueueDescription]:
        """
        List all queues with pagination.
        
        Args:
            skip: Number of queues to skip
            top: Maximum number of queues to return
            
        Returns:
            List of QueueDescription objects
        """
        async with self._lock:
            queues = list(self._queues.values())
            # Sort by name for consistent ordering
            queues.sort(key=lambda q: q.name)
            # Apply pagination
            return queues[skip:skip + top]
    
    async def get_queue(self, name: str) -> QueueDescription:
        """
        Get a queue by name.
        
        Args:
            name: Queue name
            
        Returns:
            QueueDescription
            
        Raises:
            QueueNotFoundError: Queue not found
        """
        async with self._lock:
            if name not in self._queues:
                raise QueueNotFoundError(queue_name=name)
            
            return self._queues[name]
    
    async def update_queue(
        self,
        name: str,
        properties: QueueProperties,
    ) -> QueueDescription:
        """
        Update queue properties.
        
        Args:
            name: Queue name
            properties: New queue properties
            
        Returns:
            Updated QueueDescription
            
        Raises:
            QueueNotFoundError: Queue not found
        """
        async with self._lock:
            if name not in self._queues:
                raise QueueNotFoundError(queue_name=name)
            
            queue = self._queues[name]
            queue.properties = properties
            queue.updated_at = datetime.now(timezone.utc)
            
            return queue
    
    async def delete_queue(self, name: str) -> None:
        """
        Delete a queue and all its messages.
        
        Args:
            name: Queue name
            
        Raises:
            QueueNotFoundError: Queue not found
        """
        async with self._lock:
            if name not in self._queues:
                raise QueueNotFoundError(queue_name=name)
            
            # Delete queue and all messages
            del self._queues[name]
            del self._messages[name]
            
            # Audit log
            self._audit_logger.log_queue_deleted(queue_name=name)
    
    async def get_queue_count(self) -> int:
        """
        Get the total number of queues.
        
        Returns:
            Number of queues
        """
        async with self._lock:
            return len(self._queues)
    
    async def update_runtime_info(
        self,
        name: str,
        runtime_info: QueueRuntimeInfo,
    ) -> None:
        """
        Update queue runtime information.
        
        Args:
            name: Queue name
            runtime_info: New runtime information
            
        Raises:
            QueueNotFoundError: Queue not found
        """
        async with self._lock:
            if name not in self._queues:
                raise QueueNotFoundError(queue_name=name)
            
            self._queues[name].runtime_info = runtime_info
    
    async def reset(self) -> None:
        """Reset the backend, clearing all queues and messages."""
        async with self._lock:
            self._queues.clear()
            self._messages.clear()
            self._dead_letter_messages.clear()
            self._locked_messages.clear()
            self._sequence_counters.clear()
    
    async def send_message(
        self, 
        queue_name: str, 
        request: SendMessageRequest
    ) -> ServiceBusMessage:
        """
        Send a message to a Service Bus queue.
        
        Args:
            queue_name: Name of the queue
            request: Message send request
            
        Returns:
            The created message with system properties
            
        Raises:
            QueueNotFoundError: If the queue does not exist
            MessageSizeExceededError: If message exceeds size limit
            QuotaExceededError: If rate limit exceeded
        """
        import time
        start_time = time.perf_counter()
        
        try:
            # Validate message size and properties
            message_dict = {
                "body": request.body,
                "properties": request.user_properties or {},
                "content_type": request.content_type,
            }
            self._message_validator.validate_message_size(message_dict)
            if request.user_properties:
                self._message_validator.validate_user_properties(request.user_properties)
            
            # Validate session ID if provided
            if request.session_id:
                self._session_validator.validate(request.session_id)
            
            # Check rate limit
            await self._rate_limiter.check_queue_rate(queue_name)
            
            async with self._lock:
                if queue_name not in self._queues:
                    raise QueueNotFoundError(queue_name=queue_name)
                
                queue = self._queues[queue_name]
                
                # Get next sequence number
                if queue_name not in self._sequence_counters:
                    self._sequence_counters[queue_name] = 1
            sequence_number = self._sequence_counters[queue_name]
            self._sequence_counters[queue_name] += 1
            
            # Create message
            now = datetime.now(timezone.utc)
            message = ServiceBusMessage(
                message_id=str(uuid.uuid4()),
                session_id=request.session_id,
                correlation_id=request.correlation_id,
                content_type=request.content_type,
                label=request.label,
                to=request.to,
                reply_to=request.reply_to,
                time_to_live=request.time_to_live or queue.properties.default_message_time_to_live,
                scheduled_enqueue_time_utc=request.scheduled_enqueue_time_utc,
                user_properties=request.user_properties,
                body=request.body,
                enqueued_time_utc=now,
                sequence_number=sequence_number,
                delivery_count=0,
            )
            
            # Add to queue
            if queue_name not in self._messages:
                self._messages[queue_name] = []
            self._messages[queue_name].append(message)
            
            # Update runtime info
            await self._update_runtime_info(queue_name)
            
            # Log message sent
            self._logger.log_message_operation(
                operation="message_sent",
                entity_type="queue",
                entity_name=queue_name,
                message_id=message.message_id,
                sequence_number=message.sequence_number,
                message_size=len(message.body.encode('utf-8')) if message.body else 0,
                session_id=message.session_id
            )
            
            # Track metrics
            duration = time.perf_counter() - start_time
            message_size = len(message.body.encode('utf-8')) if message.body else 0
            self._metrics.track_message_sent('queue', queue_name, message_size, duration)
            
            return message
        except Exception as e:
            # Track error
            self._metrics.track_error('send_message', type(e).__name__)
            raise
    
    async def receive_message(
        self,
        queue_name: str,
        mode: str = ReceiveMode.PEEK_LOCK
    ) -> Optional[ServiceBusMessage]:
        """
        Receive a message from a Service Bus queue.
        
        Args:
            queue_name: Name of the queue
            mode: Receive mode (PeekLock or ReceiveAndDelete)
            
        Returns:
            A message if available, None otherwise
            
        Raises:
            QueueNotFoundError: If the queue does not exist
        """
        import time
        start_time = time.perf_counter()
        
        try:
            async with self._lock:
                if queue_name not in self._queues:
                    raise QueueNotFoundError(queue_name=queue_name)
                
                # Check for expired locks and return them to queue
                await self._check_expired_locks(queue_name)
                
                if queue_name not in self._messages or not self._messages[queue_name]:
                    return None
                
                # Get first available message
                message = self._messages[queue_name][0]
                
                if mode == ReceiveMode.RECEIVE_AND_DELETE:
                    # Remove message immediately
                    self._messages[queue_name].pop(0)
                    await self._update_runtime_info(queue_name)
                    return message
                
                # PeekLock mode - lock the message
                queue = self._queues[queue_name]
                lock_token = str(uuid.uuid4())
                locked_until = datetime.now(timezone.utc) + timedelta(seconds=queue.properties.lock_duration)
                
                message.lock_token = lock_token
                message.locked_until_utc = locked_until
                message.is_locked = True
                message.delivery_count += 1
                
                # Move to locked messages
                self._messages[queue_name].pop(0)
                if queue_name not in self._locked_messages:
                    self._locked_messages[queue_name] = {}
                self._locked_messages[queue_name][lock_token] = (message, locked_until)
                
                await self._update_runtime_info(queue_name)
                
                # Log message received
                self._logger.log_message_operation(
                    operation="message_received",
                    entity_type="queue",
                    entity_name=queue_name,
                    message_id=message.message_id,
                    sequence_number=message.sequence_number,
                    delivery_count=message.delivery_count,
                    session_id=message.session_id,
                    lock_token=lock_token
                )
                
                # Track metrics
                duration = time.perf_counter() - start_time
                self._metrics.track_message_received('queue', queue_name, duration)
                
                return message
        except Exception as e:
            # Track error
            self._metrics.track_error('receive_message', type(e).__name__)
            raise
    
    async def complete_message(
        self,
        queue_name: str,
        message_id: str,
        lock_token: str
    ):
        """
        Complete a message and remove it from the queue.
        
        Args:
            queue_name: Name of the queue
            message_id: ID of the message
            lock_token: Lock token of the message
            
        Raises:
            QueueNotFoundError: If the queue does not exist
            MessageNotFoundError: If the message is not found
            MessageLockLostError: If the lock token is invalid or expired
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(queue_name=queue_name)
            
            # Check for expired locks
            await self._check_expired_locks(queue_name)
            
            # Find locked message (this validates existence before format)
            if (queue_name not in self._locked_messages
                    or lock_token not in self._locked_messages[queue_name]):
                raise MessageLockLostError(
                    "Message lock token is invalid or expired"
                )
            
            # Validate lock token format (for future use)
            try:
                self._lock_token_validator.validate_format(lock_token)
            except InvalidOperationError:
                # Already validated by existence check, format is secondary
                pass
            
            message, _ = self._locked_messages[queue_name][lock_token]
            
            if message.message_id != message_id:
                raise MessageNotFoundError("Message ID does not match lock token", queue_name)
            
            # Remove from locked messages
            del self._locked_messages[queue_name][lock_token]
            
            # Log message completed
            self._logger.log_message_operation(
                operation="message_completed",
                entity_type="queue",
                entity_name=queue_name,
                message_id=message.message_id,
                sequence_number=message.sequence_number,
                lock_token=lock_token
            )
            
            # Track metrics
            self._metrics.track_message_completed('queue', queue_name)
            
            await self._update_runtime_info(queue_name)
    
    async def abandon_message(
        self,
        queue_name: str,
        message_id: str,
        lock_token: str
    ):
        """
        Abandon a message and return it to the queue.
        
        Args:
            queue_name: Name of the queue
            message_id: ID of the message
            lock_token: Lock token of the message
            
        Raises:
            QueueNotFoundError: If the queue does not exist
            MessageNotFoundError: If the message is not found
            MessageLockLostError: If the lock token is invalid or expired
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(queue_name=queue_name)
            
            # Check for expired locks
            await self._check_expired_locks(queue_name)
            
            # Find locked message
            if queue_name not in self._locked_messages or lock_token not in self._locked_messages[queue_name]:
                raise MessageLockLostError("Message lock token is invalid or expired")
            
            message, _ = self._locked_messages[queue_name][lock_token]
            
            if message.message_id != message_id:
                raise MessageNotFoundError("Message ID does not match lock token")
            
            # Check if max delivery count exceeded
            queue = self._queues[queue_name]
            if message.delivery_count >= queue.properties.max_delivery_count:
                # Move to dead-letter queue
                await self._move_to_dead_letter(queue_name, message, "MaxDeliveryCountExceeded", "The message has exceeded the maximum delivery count")
            else:
                # Return to queue
                message.is_locked = False
                message.lock_token = None
                message.locked_until_utc = None
                
                if queue_name not in self._messages:
                    self._messages[queue_name] = []
                self._messages[queue_name].append(message)
            
            # Remove from locked messages
            del self._locked_messages[queue_name][lock_token]
            
            # Log message abandoned
            self._logger.log_message_operation(
                operation="message_abandoned",
                entity_type="queue",
                entity_name=queue_name,
                message_id=message.message_id,
                sequence_number=message.sequence_number,
                delivery_count=message.delivery_count,
                lock_token=lock_token,
                returned_to_queue=message.delivery_count < queue.properties.max_delivery_count
            )
            
            # Track metrics
            self._metrics.track_message_abandoned('queue', queue_name)
            
            await self._update_runtime_info(queue_name)
    
    async def dead_letter_message(
        self,
        queue_name: str,
        message_id: str,
        lock_token: str,
        reason: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        Move a message to the dead-letter queue.
        
        Args:
            queue_name: Name of the queue
            message_id: ID of the message
            lock_token: Lock token of the message
            reason: Reason for dead-lettering
            description: Description of why the message was dead-lettered
            
        Raises:
            QueueNotFoundError: If the queue does not exist
            MessageNotFoundError: If the message is not found
            MessageLockLostError: If the lock token is invalid or expired
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(queue_name=queue_name)
            
            # Check for expired locks
            await self._check_expired_locks(queue_name)
            
            # Find locked message
            if queue_name not in self._locked_messages or lock_token not in self._locked_messages[queue_name]:
                raise MessageLockLostError("Message lock token is invalid or expired")
            
            message, _ = self._locked_messages[queue_name][lock_token]
            
            if message.message_id != message_id:
                raise MessageNotFoundError("Message ID does not match lock token")
            
            # Move to dead-letter queue
            await self._move_to_dead_letter(queue_name, message, reason, description)
            
            # Remove from locked messages
            del self._locked_messages[queue_name][lock_token]
            
            # Log message dead-lettered
            self._logger.log_message_operation(
                operation="message_dead_lettered",
                entity_type="queue",
                entity_name=queue_name,
                message_id=message.message_id,
                sequence_number=message.sequence_number,
                lock_token=lock_token,
                reason=reason or "Unknown",
                description=description
            )
            
            # Track metrics
            self._metrics.track_message_deadlettered('queue', queue_name, reason or "Unknown")
            
            await self._update_runtime_info(queue_name)
    
    async def renew_lock(
        self,
        queue_name: str,
        message_id: str,
        lock_token: str
    ) -> datetime:
        """
        Renew the lock on a message.
        
        Args:
            queue_name: Name of the queue
            message_id: ID of the message
            lock_token: Lock token of the message
            
        Returns:
            New locked_until timestamp
            
        Raises:
            QueueNotFoundError: If the queue does not exist
            MessageNotFoundError: If the message is not found
            MessageLockLostError: If the lock token is invalid or expired
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(queue_name=queue_name)
            
            # Check for expired locks
            await self._check_expired_locks(queue_name)
            
            # Find locked message
            if queue_name not in self._locked_messages or lock_token not in self._locked_messages[queue_name]:
                raise MessageLockLostError("Message lock token is invalid or expired")
            
            message, _ = self._locked_messages[queue_name][lock_token]
            
            if message.message_id != message_id:
                raise MessageNotFoundError("Message ID does not match lock token")
            
            # Renew lock
            queue = self._queues[queue_name]
            new_locked_until = datetime.now(timezone.utc) + timedelta(seconds=queue.properties.lock_duration)
            message.locked_until_utc = new_locked_until
            self._locked_messages[queue_name][lock_token] = (message, new_locked_until)
            
            # Log lock renewal
            self._logger.log_lock_operation(
                operation="lock_renewed",
                entity_type="queue",
                entity_name=queue_name,
                message_id=message.message_id,
                lock_token=lock_token,
                locked_until=new_locked_until.isoformat()
            )
            
            return new_locked_until
    
    async def _check_expired_locks(self, queue_name: str):
        """
        Check for expired locks and return messages to the queue.
        
        Args:
            queue_name: Name of the queue
        """
        if queue_name not in self._locked_messages:
            return
        
        now = datetime.now(timezone.utc)
        expired_tokens = []
        
        for lock_token, (message, locked_until) in self._locked_messages[queue_name].items():
            if now >= locked_until:
                expired_tokens.append(lock_token)
        
        # Process expired locks
        for lock_token in expired_tokens:
            message, _ = self._locked_messages[queue_name][lock_token]
            
            # Log lock expired
            self._logger.log_lock_operation(
                operation="lock_expired",
                entity_type="queue",
                entity_name=queue_name,
                message_id=message.message_id,
                lock_token=lock_token,
                delivery_count=message.delivery_count
            )
            
            # Check if max delivery count exceeded
            queue = self._queues[queue_name]
            if message.delivery_count >= queue.properties.max_delivery_count:
                # Move to dead-letter queue
                await self._move_to_dead_letter(queue_name, message, "MaxDeliveryCountExceeded", "The message has exceeded the maximum delivery count")
            else:
                # Return to queue
                message.is_locked = False
                message.lock_token = None
                message.locked_until_utc = None
                
                if queue_name not in self._messages:
                    self._messages[queue_name] = []
                self._messages[queue_name].append(message)
            
            del self._locked_messages[queue_name][lock_token]
    
    async def _move_to_dead_letter(
        self,
        queue_name: str,
        message: ServiceBusMessage,
        reason: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        Move a message to the dead-letter queue.
        
        Args:
            queue_name: Name of the queue
            message: Message to move
            reason: Reason for dead-lettering
            description: Description
        """
        message.is_dead_lettered = True
        message.is_locked = False
        message.lock_token = None
        message.locked_until_utc = None
        message.dead_letter_reason = reason
        message.dead_letter_description = description
        
        if queue_name not in self._dead_letter_messages:
            self._dead_letter_messages[queue_name] = []
        self._dead_letter_messages[queue_name].append(message)
    
    async def _update_runtime_info(self, queue_name: str):
        """
        Update queue runtime information.
        
        Args:
            queue_name: Queue name
        """
        if queue_name not in self._queues:
            return
        
        queue = self._queues[queue_name]
        active_count = len(self._messages.get(queue_name, []))
        locked_count = len(self._locked_messages.get(queue_name, {}))
        dead_letter_count = len(self._dead_letter_messages.get(queue_name, []))
        total_count = active_count + locked_count
        
        queue.runtime_info = QueueRuntimeInfo(
            message_count=total_count,
            active_message_count=active_count,
            dead_letter_message_count=dead_letter_count,
            scheduled_message_count=0,
            transfer_message_count=0,
            transfer_dead_letter_message_count=0,
            size_in_bytes=0,
        )
    
    # ========== Topic Operations ==========
    
    async def create_topic(
        self,
        name: str,
        properties: Optional[TopicProperties] = None,
    ) -> TopicDescription:
        """
        Create a new Service Bus topic.
        
        Args:
            name: Topic name
            properties: Optional topic properties
            
        Returns:
            TopicDescription: The created topic
            
        Raises:
            TopicAlreadyExistsError: If topic already exists
            QuotaExceededError: If max topics reached
            InvalidEntityNameError: If topic name is invalid
        """
        # Validate topic name
        self._entity_validator.validate_topic_name(name)
        
        async with self._lock:
            if name in self._topics:
                raise TopicAlreadyExistsError(f"Topic '{name}' already exists")
            
            if len(self._topics) >= self._max_topics:
                raise QuotaExceededError("topic_count", len(self._topics), self._max_topics)
            
            now = datetime.now(timezone.utc)
            
            if properties is None:
                properties = TopicProperties()
            
            runtime_info = TopicRuntimeInfo(
                subscription_count=0,
                size_in_bytes=0,
                scheduled_message_count=0,
            )
            
            topic = TopicDescription(
                name=name,
                properties=properties,
                runtime_info=runtime_info,
                created_at=now,
                updated_at=now,
            )
            
            self._topics[name] = topic
            return topic
    
    async def list_topics(self) -> List[TopicDescription]:
        """
        List all Service Bus topics.
        
        Returns:
            List[TopicDescription]: List of all topics
        """
        async with self._lock:
            return list(self._topics.values())
    
    async def get_topic(self, name: str) -> TopicDescription:
        """
        Get a Service Bus topic by name.
        
        Args:
            name: Topic name
            
        Returns:
            TopicDescription: The requested topic
            
        Raises:
            TopicNotFoundError: If topic not found
        """
        async with self._lock:
            if name not in self._topics:
                raise TopicNotFoundError(f"Topic '{name}' not found")
            return self._topics[name]
    
    async def update_topic(
        self,
        name: str,
        properties: TopicProperties,
    ) -> TopicDescription:
        """
        Update an existing Service Bus topic.
        
        Args:
            name: Topic name
            properties: Updated topic properties
            
        Returns:
            TopicDescription: The updated topic
            
        Raises:
            TopicNotFoundError: If topic not found
        """
        async with self._lock:
            if name not in self._topics:
                raise TopicNotFoundError(f"Topic '{name}' not found")
            
            topic = self._topics[name]
            topic.properties = properties
            topic.updated_at = datetime.now(timezone.utc)
            
            return topic
    
    async def delete_topic(self, name: str):
        """
        Delete a Service Bus topic and all its subscriptions.
        
        Args:
            name: Topic name
            
        Raises:
            TopicNotFoundError: If topic not found
        """
        async with self._lock:
            if name not in self._topics:
                raise TopicNotFoundError(f"Topic '{name}' not found")
            
            # Delete all subscriptions for this topic
            subscriptions_to_delete = [
                (topic, sub) for topic, sub in self._subscriptions.keys()
                if topic == name
            ]
            
            for key in subscriptions_to_delete:
                del self._subscriptions[key]
                self._subscription_messages.pop(key, None)
                self._subscription_locked.pop(key, None)
                self._subscription_dead_letter.pop(key, None)
            
            del self._topics[name]
    
    # ========== Subscription Operations ==========
    
    async def create_subscription(
        self,
        topic_name: str,
        subscription_name: str,
        properties: Optional[SubscriptionProperties] = None,
    ) -> SubscriptionDescription:
        """
        Create a new subscription under a topic.
        
        Args:
            topic_name: Parent topic name
            subscription_name: Subscription name
            properties: Optional subscription properties
            
        Returns:
            SubscriptionDescription: The created subscription
            
        Raises:
            TopicNotFoundError: If parent topic not found
            SubscriptionAlreadyExistsError: If subscription already exists
            InvalidEntityNameError: If subscription name is invalid
            QuotaExceededError: If max subscriptions per topic exceeded
        """
        # Validate subscription name
        self._entity_validator.validate_subscription_name(subscription_name)
        
        async with self._lock:
            if topic_name not in self._topics:
                raise TopicNotFoundError(f"Topic '{topic_name}' not found")
            
            # Check subscription count for this topic
            existing_subs = [s for (t, _), s in self._subscriptions.items() if t == topic_name]
            if len(existing_subs) >= MAX_SUBSCRIPTIONS_PER_TOPIC:
                raise QuotaExceededError(
                    "subscription_count",
                    len(existing_subs),
                    MAX_SUBSCRIPTIONS_PER_TOPIC,
                    entity_name=topic_name
                )
            
            key = (topic_name, subscription_name)
            if key in self._subscriptions:
                raise SubscriptionAlreadyExistsError(topic_name, subscription_name)
            
            now = datetime.now(timezone.utc)
            
            if properties is None:
                properties = SubscriptionProperties()
            
            runtime_info = SubscriptionRuntimeInfo(
                message_count=0,
                active_message_count=0,
                dead_letter_message_count=0,
            )
            
            # Create default TrueFilter rule
            default_filter = SubscriptionFilter(filter_type=FilterType.TRUE_FILTER)
            default_rule = RuleDescription(
                name="$Default",
                filter=default_filter,
                created_at=now,
            )
            
            subscription = SubscriptionDescription(
                topic_name=topic_name,
                subscription_name=subscription_name,
                properties=properties,
                runtime_info=runtime_info,
                rules=[default_rule],
                created_at=now,
                updated_at=now,
            )
            
            self._subscriptions[key] = subscription
            self._subscription_messages[key] = []
            self._subscription_locked[key] = {}
            self._subscription_dead_letter[key] = []
            
            # Update topic subscription count
            await self._update_topic_runtime_info(topic_name)
            
            return subscription
    
    async def list_subscriptions(self, topic_name: str) -> List[SubscriptionDescription]:
        """
        List all subscriptions for a topic.
        
        Args:
            topic_name: Topic name
            
        Returns:
            List[SubscriptionDescription]: List of subscriptions
            
        Raises:
            TopicNotFoundError: If topic not found
        """
        async with self._lock:
            if topic_name not in self._topics:
                raise TopicNotFoundError(f"Topic '{topic_name}' not found")
            
            return [
                sub for (t, _), sub in self._subscriptions.items()
                if t == topic_name
            ]
    
    async def get_subscription(
        self,
        topic_name: str,
        subscription_name: str
    ) -> SubscriptionDescription:
        """
        Get a subscription by name.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            
        Returns:
            SubscriptionDescription: The requested subscription
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError(topic_name, subscription_name)
            return self._subscriptions[key]
    
    async def update_subscription(
        self,
        topic_name: str,
        subscription_name: str,
        properties: SubscriptionProperties,
    ) -> SubscriptionDescription:
        """
        Update an existing subscription.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            properties: Updated subscription properties
            
        Returns:
            SubscriptionDescription: The updated subscription
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            subscription = self._subscriptions[key]
            subscription.properties = properties
            subscription.updated_at = datetime.now(timezone.utc)
            
            return subscription
    
    async def delete_subscription(
        self,
        topic_name: str,
        subscription_name: str
    ):
        """
        Delete a subscription.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            del self._subscriptions[key]
            self._subscription_messages.pop(key, None)
            self._subscription_locked.pop(key, None)
            self._subscription_dead_letter.pop(key, None)
            
            # Update topic subscription count
            await self._update_topic_runtime_info(topic_name)
    
    async def _update_topic_runtime_info(self, topic_name: str):
        """
        Update topic runtime information.
        
        Args:
            topic_name: Topic name
        """
        if topic_name not in self._topics:
            return
        
        topic = self._topics[topic_name]
        subscription_count = sum(
            1 for t, _ in self._subscriptions.keys()
            if t == topic_name
        )
        
        topic.runtime_info = TopicRuntimeInfo(
            subscription_count=subscription_count,
            size_in_bytes=0,
            scheduled_message_count=0,
        )
    
    # ========== Rule Operations ==========
    
    async def add_rule(
        self,
        topic_name: str,
        subscription_name: str,
        rule_name: str,
        filter: SubscriptionFilter,
    ) -> RuleDescription:
        """
        Add a rule to a subscription.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            rule_name: Rule name
            filter: Subscription filter
            
        Returns:
            RuleDescription: The created rule
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
            RuleAlreadyExistsError: If rule already exists
            InvalidOperationError: If SQL filter contains dangerous keywords
        """
        # Validate SQL filter if present
        if filter.filter_type == FilterType.SQL_FILTER and filter.sql_expression:
            self._sql_sanitizer.validate_sql_filter(filter.sql_expression)
        
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            subscription = self._subscriptions[key]
            
            # Check if rule already exists
            if any(r.name == rule_name for r in subscription.rules):
                raise RuleAlreadyExistsError(rule_name, subscription_name)
            
            rule = RuleDescription(
                name=rule_name,
                filter=filter,
                created_at=datetime.now(timezone.utc),
            )
            
            subscription.rules.append(rule)
            subscription.updated_at = datetime.now(timezone.utc)
            
            return rule
    
    async def update_rule(
        self,
        topic_name: str,
        subscription_name: str,
        rule_name: str,
        filter: SubscriptionFilter,
    ) -> RuleDescription:
        """
        Update an existing rule.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            rule_name: Rule name
            filter: Updated subscription filter
            
        Returns:
            RuleDescription: The updated rule
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
            RuleNotFoundError: If rule not found
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            subscription = self._subscriptions[key]
            
            # Find the rule
            rule = None
            for r in subscription.rules:
                if r.name == rule_name:
                    rule = r
                    break
            
            if rule is None:
                raise RuleNotFoundError(rule_name, subscription_name)
            
            rule.filter = filter
            subscription.updated_at = datetime.now(timezone.utc)
            
            return rule
    
    async def delete_rule(
        self,
        topic_name: str,
        subscription_name: str,
        rule_name: str
    ):
        """
        Delete a rule from a subscription.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            rule_name: Rule name
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
            RuleNotFoundError: If rule not found
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            subscription = self._subscriptions[key]
            
            # Find and remove the rule
            rule_index = None
            for i, r in enumerate(subscription.rules):
                if r.name == rule_name:
                    rule_index = i
                    break
            
            if rule_index is None:
                raise RuleNotFoundError(rule_name, subscription_name)
            
            subscription.rules.pop(rule_index)
            subscription.updated_at = datetime.now(timezone.utc)
    
    async def list_rules(
        self,
        topic_name: str,
        subscription_name: str
    ) -> List[RuleDescription]:
        """
        List all rules for a subscription.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            
        Returns:
            List[RuleDescription]: List of rules
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            return self._subscriptions[key].rules.copy()
    
    # ========== Filter Evaluation ==========
    
    def _evaluate_true_filter(self, message: ServiceBusMessage) -> bool:
        """Always returns True - matches all messages."""
        return True
    
    def _evaluate_false_filter(self, message: ServiceBusMessage) -> bool:
        """Always returns False - matches no messages."""
        return False
    
    def _evaluate_correlation_filter(
        self,
        filter_obj: SubscriptionFilter,
        message: ServiceBusMessage
    ) -> bool:
        """
        Evaluate correlation filter against a message.
        
        A correlation filter matches if all specified properties match.
        If a filter property is None, it's not checked.
        
        Args:
            filter_obj: Correlation filter
            message: Message to evaluate
            
        Returns:
            bool: True if message matches filter
        """
        # Check standard properties
        if (filter_obj.correlation_id is not None
                and message.correlation_id != filter_obj.correlation_id):
            return False
        
        if (filter_obj.content_type is not None
                and message.content_type != filter_obj.content_type):
            return False
        
        if filter_obj.label is not None and message.label != filter_obj.label:
            return False
        
        if (filter_obj.message_id is not None
                and message.message_id != filter_obj.message_id):
            return False
        
        if (filter_obj.reply_to is not None
                and message.reply_to != filter_obj.reply_to):
            return False
        
        if (filter_obj.session_id is not None
                and message.session_id != filter_obj.session_id):
            return False
        
        if filter_obj.to is not None and message.to != filter_obj.to:
            return False
        
        # Check user properties
        if filter_obj.properties:
            if message.user_properties is None:
                return False
            
            for key, value in filter_obj.properties.items():
                if (key not in message.user_properties
                        or message.user_properties[key] != value):
                    return False
        
        return True
    
    def _evaluate_sql_filter(
        self,
        filter_obj: SubscriptionFilter,
        message: ServiceBusMessage
    ) -> bool:
        """
        Evaluate SQL filter expression against a message.
        
        Delegates to SqlFilterEvaluator for actual evaluation logic.
        
        Args:
            filter_obj: SQL filter
            message: Message to evaluate
            
        Returns:
            True if message matches filter
        """
        return self._filter_evaluator.evaluate(filter_obj, message)
    
    def _message_matches_subscription(
        self,
        subscription: SubscriptionDescription,
        message: ServiceBusMessage
    ) -> bool:
        """
        Check if a message matches any rule in a subscription.
        
        Args:
            subscription: Subscription to check
            message: Message to evaluate
            
        Returns:
            bool: True if message matches at least one rule
        """
        # If no rules, default to TrueFilter (matches all messages)
        # This matches Azure Service Bus behavior
        if not subscription.rules:
            return True
        
        # Check each rule - if any matches, the message is accepted
        for rule in subscription.rules:
            rule_filter = rule.filter
            
            if rule_filter.filter_type == FilterType.TRUE_FILTER:
                if self._evaluate_true_filter(message):
                    return True
            
            elif rule_filter.filter_type == FilterType.FALSE_FILTER:
                if self._evaluate_false_filter(message):
                    return True
            
            elif rule_filter.filter_type == FilterType.CORRELATION_FILTER:
                if self._evaluate_correlation_filter(rule_filter, message):
                    return True
            
            elif rule_filter.filter_type == FilterType.SQL_FILTER:
                if self._evaluate_sql_filter(rule_filter, message):
                    return True
        
        return False
    
    # ========== Topic Message Operations ==========
    
    async def send_to_topic(
        self,
        topic_name: str,
        message_request: SendMessageRequest,
    ) -> ServiceBusMessage:
        """
        Send a message to a topic (fan-out to matching subscriptions).
        
        Args:
            topic_name: Topic name
            message_request: Message to send
            
        Returns:
            ServiceBusMessage: The sent message
            
        Raises:
            TopicNotFoundError: If topic not found
        """
        async with self._lock:
            if topic_name not in self._topics:
                raise TopicNotFoundError(f"Topic '{topic_name}' not found")
            
            # Create the message
            now = datetime.now(timezone.utc)
            message_id = str(uuid.uuid4())
            
            message = ServiceBusMessage(
                message_id=message_id,
                body=message_request.body,
                content_type=message_request.content_type,
                correlation_id=message_request.correlation_id,
                label=message_request.label,
                to=message_request.to,
                reply_to=message_request.reply_to,
                session_id=message_request.session_id,
                time_to_live=message_request.time_to_live or 1209600,
                scheduled_enqueue_time_utc=message_request.scheduled_enqueue_time_utc,
                user_properties=message_request.user_properties,
                enqueued_time_utc=now,
                sequence_number=0,  # Will be set per subscription
                delivery_count=0,
            )
            
            # Fan out to matching subscriptions
            matched_count = 0
            for (t, sub_name), subscription in self._subscriptions.items():
                if t != topic_name:
                    continue
                
                # Check if message matches subscription filters
                matches = self._message_matches_subscription(subscription, message)
                
                if matches:
                    # Create a copy of the message for this subscription
                    sub_key = (topic_name, sub_name)
                    
                    # Get sequence number for this subscription
                    if sub_key not in self._sequence_counters:
                        self._sequence_counters[sub_key] = 1
                    
                    message_copy = ServiceBusMessage(**message.model_dump())
                    message_copy.sequence_number = self._sequence_counters[sub_key]
                    self._sequence_counters[sub_key] += 1
                    
                    # Add to subscription queue
                    if sub_key not in self._subscription_messages:
                        self._subscription_messages[sub_key] = []
                    self._subscription_messages[sub_key].append(message_copy)
                    
                    matched_count += 1
                    
                    # Update subscription runtime info
                    await self._update_subscription_runtime_info(topic_name, sub_name)
                
                # Log filter evaluation
                filter_expr = subscription.rules[0].filter.sql_expression if subscription.rules and subscription.rules[0].filter else "TrueFilter"
                self._logger.log_filter_evaluation(
                    filter_expression=filter_expr,
                    filter_result=matches,
                    message_id=message.message_id,
                    subscription_name=sub_name,
                    topic=topic_name
                )
            
            # Log topic fan-out
            self._logger.log_operation(
                operation="topic_fan_out",
                entity_type="topic",
                entity_name=topic_name,
                message_id=message.message_id,
                sequence_number=0,
                matched_subscriptions=matched_count,
                total_subscriptions=len([s for (t, _), s in self._subscriptions.items() if t == topic_name])
            )
            
            return message
    
    async def receive_from_subscription(
        self,
        topic_name: str,
        subscription_name: str,
        mode: ReceiveMode = ReceiveMode.PEEK_LOCK,
        max_messages: int = 1,
    ) -> List[ServiceBusMessage]:
        """
        Receive messages from a subscription.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            mode: Receive mode (PEEK_LOCK or RECEIVE_AND_DELETE)
            max_messages: Maximum number of messages to receive
            
        Returns:
            List of received messages (up to max_messages)
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            subscription = self._subscriptions[key]
            
            if key not in self._subscription_messages:
                self._subscription_messages[key] = []
            
            messages = self._subscription_messages[key]
            
            # Get available messages (not locked or expired locks)
            available = []
            for msg in messages:
                if not msg.is_locked or (
                    msg.locked_until_utc and 
                    msg.locked_until_utc < datetime.now(timezone.utc)
                ):
                    available.append(msg)
            
            # Limit to max_messages
            to_receive = available[:max_messages]
            
            if mode == ReceiveMode.PEEK_LOCK:
                # Lock messages
                lock_duration_seconds = subscription.properties.lock_duration or 60
                lock_duration = timedelta(seconds=lock_duration_seconds)
                now = datetime.now(timezone.utc)
                
                if key not in self._subscription_locked:
                    self._subscription_locked[key] = {}
                
                for msg in to_receive:
                    msg.is_locked = True
                    msg.lock_token = str(uuid.uuid4())
                    msg.locked_until_utc = now + lock_duration
                    msg.delivery_count += 1
                    
                    self._subscription_locked[key][msg.lock_token] = (msg, msg.locked_until_utc)
                    
                    # Check max delivery count
                    max_delivery = subscription.properties.max_delivery_count or 10
                    if msg.delivery_count >= max_delivery:
                        # Move to dead-letter
                        if subscription.properties.dead_lettering_on_message_expiration:
                            await self._move_subscription_to_dead_letter(
                                topic_name,
                                subscription_name,
                                msg,
                                "MaxDeliveryCountExceeded",
                                f"Message exceeded max delivery count of {max_delivery}"
                            )
                            messages.remove(msg)
                            del self._subscription_locked[key][msg.lock_token]
            
            elif mode == ReceiveMode.RECEIVE_AND_DELETE:
                # Remove messages immediately
                for msg in to_receive:
                    messages.remove(msg)
            
            await self._update_subscription_runtime_info(topic_name, subscription_name)
            
            return to_receive
    
    async def complete_subscription_message(
        self,
        topic_name: str,
        subscription_name: str,
        lock_token: str,
    ):
        """
        Complete a message from a subscription (remove from queue).
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            lock_token: Message lock token
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
            MessageLockLostError: If lock is invalid or expired
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            if key not in self._subscription_locked or lock_token not in self._subscription_locked[key]:
                raise MessageLockLostError("Message lock not found or expired")
            
            message, locked_until = self._subscription_locked[key][lock_token]
            
            # Check lock expiration
            if locked_until < datetime.now(timezone.utc):
                raise MessageLockLostError("Message lock has expired")
            
            # Remove message from queue
            if key in self._subscription_messages and message in self._subscription_messages[key]:
                self._subscription_messages[key].remove(message)
            
            del self._subscription_locked[key][lock_token]
            
            await self._update_subscription_runtime_info(topic_name, subscription_name)
    
    async def abandon_subscription_message(
        self,
        topic_name: str,
        subscription_name: str,
        lock_token: str,
    ):
        """
        Abandon a message from a subscription (unlock and return to queue).
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            lock_token: Message lock token
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
            MessageLockLostError: If lock is invalid or expired
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            if key not in self._subscription_locked or lock_token not in self._subscription_locked[key]:
                raise MessageLockLostError("Message lock not found or expired")
            
            message, locked_until = self._subscription_locked[key][lock_token]
            
            # Check lock expiration
            if locked_until < datetime.now(timezone.utc):
                raise MessageLockLostError("Message lock has expired")
            
            # Unlock message
            message.is_locked = False
            message.lock_token = None
            message.locked_until_utc = None
            
            del self._subscription_locked[key][lock_token]
    
    async def dead_letter_subscription_message(
        self,
        topic_name: str,
        subscription_name: str,
        lock_token: str,
        reason: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        Move a subscription message to the dead-letter queue.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            lock_token: Message lock token
            reason: Dead-letter reason
            description: Dead-letter description
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
            MessageLockLostError: If lock is invalid or expired
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            if key not in self._subscription_locked or lock_token not in self._subscription_locked[key]:
                raise MessageLockLostError("Message lock not found or expired")
            
            message, locked_until = self._subscription_locked[key][lock_token]
            
            # Check lock expiration
            if locked_until < datetime.now(timezone.utc):
                raise MessageLockLostError("Message lock has expired")
            
            # Remove from active queue
            if key in self._subscription_messages and message in self._subscription_messages[key]:
                self._subscription_messages[key].remove(message)
            
            await self._move_subscription_to_dead_letter(
                topic_name,
                subscription_name,
                message,
                reason,
                description
            )
            
            del self._subscription_locked[key][lock_token]
            
            await self._update_subscription_runtime_info(topic_name, subscription_name)
    
    async def renew_subscription_message_lock(
        self,
        topic_name: str,
        subscription_name: str,
        lock_token: str,
    ) -> datetime:
        """
        Renew the lock on a subscription message.
        
        Args:
            topic_name: Topic name
            subscription_name: Subscription name
            lock_token: Message lock token
            
        Returns:
            datetime: New lock expiration time
            
        Raises:
            SubscriptionNotFoundError: If subscription not found
            MessageLockLostError: If lock is invalid or expired
        """
        async with self._lock:
            key = (topic_name, subscription_name)
            if key not in self._subscriptions:
                raise SubscriptionNotFoundError({topic_name}, {subscription_name})
            
            if key not in self._subscription_locked or lock_token not in self._subscription_locked[key]:
                raise MessageLockLostError("Message lock not found or expired")
            
            message, locked_until = self._subscription_locked[key][lock_token]
            
            # Check lock expiration
            if locked_until < datetime.now(timezone.utc):
                raise MessageLockLostError("Message lock has expired")
            
            subscription = self._subscriptions[key]
            lock_duration_seconds = subscription.properties.lock_duration or 60
            lock_duration = timedelta(seconds=lock_duration_seconds)
            new_expiry = datetime.now(timezone.utc) + lock_duration
            
            message.locked_until_utc = new_expiry
            self._subscription_locked[key][lock_token] = (message, new_expiry)
            
            return new_expiry
    
    async def _move_subscription_to_dead_letter(
        self,
        topic_name: str,
        subscription_name: str,
        message: ServiceBusMessage,
        reason: Optional[str] = None,
        description: Optional[str] = None
    ):
        """Move a subscription message to the dead-letter queue."""
        message.is_dead_lettered = True
        message.is_locked = False
        message.lock_token = None
        message.locked_until_utc = None
        message.dead_letter_reason = reason
        message.dead_letter_description = description
        
        key = (topic_name, subscription_name)
        if key not in self._subscription_dead_letter:
            self._subscription_dead_letter[key] = []
        self._subscription_dead_letter[key].append(message)
    
    async def _update_subscription_runtime_info(
        self,
        topic_name: str,
        subscription_name: str
    ):
        """Update subscription runtime information."""
        key = (topic_name, subscription_name)
        if key not in self._subscriptions:
            return
        
        subscription = self._subscriptions[key]
        active_count = len(self._subscription_messages.get(key, []))
        locked_count = len(self._subscription_locked.get(key, {}))
        dead_letter_count = len(self._subscription_dead_letter.get(key, []))
        total_count = active_count + locked_count
        
        subscription.runtime_info = SubscriptionRuntimeInfo(
            message_count=total_count,
            active_message_count=active_count,
            dead_letter_message_count=dead_letter_count,
        )
