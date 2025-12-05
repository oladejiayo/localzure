"""
Queue Storage Backend

In-memory queue storage backend with async operations.

Author: Ayodele Oladeji
Date: 2025
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .models import Queue, QueueMetadata, QueueProperties, QueueNameValidator, Message


# Custom exceptions
class QueueAlreadyExistsError(Exception):
    """Raised when attempting to create a queue that already exists."""
    pass


class QueueNotFoundError(Exception):
    """Raised when queue is not found."""
    pass


class InvalidQueueNameError(Exception):
    """Raised when queue name is invalid."""
    pass


class MessageNotFoundError(Exception):
    """Raised when message is not found."""
    pass


class InvalidPopReceiptError(Exception):
    """Raised when pop receipt is invalid."""
    pass


class QueueBackend:
    """
    In-memory queue storage backend.
    
    Provides async operations for queue management with thread safety.
    """
    
    def __init__(self):
        """Initialize the queue backend."""
        self._queues: Dict[str, Queue] = {}
        self._messages: Dict[str, List[Message]] = {}  # queue_name -> list of Message objects
        self._lock = asyncio.Lock()
    
    async def create_queue(
        self,
        queue_name: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Queue:
        """
        Create a new queue.
        
        Args:
            queue_name: Name of the queue
            metadata: Optional metadata key-value pairs
            
        Returns:
            Created queue
            
        Raises:
            InvalidQueueNameError: If queue name is invalid
            QueueAlreadyExistsError: If queue already exists
        """
        async with self._lock:
            # Validate queue name
            is_valid, error = QueueNameValidator.validate(queue_name)
            if not is_valid:
                raise InvalidQueueNameError(error)
            
            # Check if queue already exists
            if queue_name in self._queues:
                raise QueueAlreadyExistsError(f"Queue '{queue_name}' already exists")
            
            # Create queue
            queue = Queue(
                name=queue_name,
                metadata=QueueMetadata(metadata=metadata or {}),
                properties=QueueProperties(approximate_message_count=0),
            )
            
            self._queues[queue_name] = queue
            self._messages[queue_name] = []
            
            return queue
    
    async def get_queue(self, queue_name: str) -> Queue:
        """
        Get a queue by name.
        
        Args:
            queue_name: Queue name
            
        Returns:
            Queue object
            
        Raises:
            QueueNotFoundError: If queue not found
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(f"Queue '{queue_name}' not found")
            return self._queues[queue_name]
    
    async def list_queues(
        self,
        prefix: Optional[str] = None,
        max_results: Optional[int] = None,
        marker: Optional[str] = None,
        include_metadata: bool = False,
    ) -> Tuple[List[Queue], Optional[str]]:
        """
        List queues with optional filtering and pagination.
        
        Args:
            prefix: Optional prefix filter
            max_results: Maximum number of results to return
            marker: Continuation token
            include_metadata: Whether to include metadata in response
            
        Returns:
            Tuple of (queues list, next_marker)
        """
        async with self._lock:
            # Get all queue names sorted
            all_queue_names = sorted(self._queues.keys())
            
            # Apply prefix filter
            if prefix:
                all_queue_names = [name for name in all_queue_names if name.startswith(prefix)]
            
            # Apply marker (continuation)
            if marker:
                try:
                    marker_index = all_queue_names.index(marker)
                    all_queue_names = all_queue_names[marker_index + 1:]
                except ValueError:
                    # Invalid marker, start from beginning
                    pass
            
            # Apply max_results
            next_marker = None
            if max_results and len(all_queue_names) > max_results:
                next_marker = all_queue_names[max_results - 1]
                all_queue_names = all_queue_names[:max_results]
            
            # Get queue objects
            queues = []
            for name in all_queue_names:
                queue = self._queues[name]
                # Update message count from messages storage
                queue.properties.approximate_message_count = len(self._messages.get(name, []))
                
                # If not including metadata, create a copy without it
                if not include_metadata:
                    queue_copy = Queue(
                        name=queue.name,
                        metadata=QueueMetadata(metadata={}),
                        properties=queue.properties,
                        created_time=queue.created_time,
                    )
                    queues.append(queue_copy)
                else:
                    queues.append(queue)
            
            return queues, next_marker
    
    async def get_queue_metadata(self, queue_name: str) -> Tuple[QueueMetadata, QueueProperties]:
        """
        Get queue metadata and properties.
        
        Args:
            queue_name: Queue name
            
        Returns:
            Tuple of (metadata, properties)
            
        Raises:
            QueueNotFoundError: If queue not found
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(f"Queue '{queue_name}' not found")
            
            queue = self._queues[queue_name]
            # Update message count
            queue.properties.approximate_message_count = len(self._messages.get(queue_name, []))
            
            return queue.metadata, queue.properties
    
    async def set_queue_metadata(
        self,
        queue_name: str,
        metadata: Dict[str, str],
    ) -> None:
        """
        Set queue metadata.
        
        Args:
            queue_name: Queue name
            metadata: Metadata key-value pairs
            
        Raises:
            QueueNotFoundError: If queue not found
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(f"Queue '{queue_name}' not found")
            
            self._queues[queue_name].metadata = QueueMetadata(metadata=metadata)
    
    async def delete_queue(self, queue_name: str) -> None:
        """
        Delete a queue and all its messages.
        
        Args:
            queue_name: Queue name
            
        Raises:
            QueueNotFoundError: If queue not found
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(f"Queue '{queue_name}' not found")
            
            del self._queues[queue_name]
            if queue_name in self._messages:
                del self._messages[queue_name]
    
    async def reset(self) -> None:
        """Reset the backend, clearing all queues and messages."""
        async with self._lock:
            self._queues.clear()
            self._messages.clear()
    
    # Message Operations
    
    async def put_message(
        self,
        queue_name: str,
        message_text: str,
        visibility_timeout: int = 0,
        message_ttl: int = 604800,
    ) -> Message:
        """
        Put a message into the queue.
        
        Args:
            queue_name: Queue name
            message_text: Message content (will be base64-encoded)
            visibility_timeout: Seconds until message becomes visible (default: 0)
            message_ttl: Message time-to-live in seconds (default: 7 days)
            
        Returns:
            Created message
            
        Raises:
            QueueNotFoundError: If queue not found
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(f"Queue '{queue_name}' not found")
            
            # Create message
            message = Message.create(
                message_text=message_text,
                visibility_timeout=visibility_timeout,
                message_ttl=message_ttl,
            )
            
            # Add to messages list
            self._messages[queue_name].append(message)
            
            # Update queue message count
            self._queues[queue_name].properties.approximate_message_count = len(self._messages[queue_name])
            
            return message
    
    async def get_messages(
        self,
        queue_name: str,
        num_messages: int = 1,
        visibility_timeout: int = 30,
    ) -> List[Message]:
        """
        Get messages from the queue with visibility timeout.
        
        Args:
            queue_name: Queue name
            num_messages: Number of messages to retrieve (1-32)
            visibility_timeout: Visibility timeout in seconds (default: 30)
            
        Returns:
            List of messages (may be fewer than requested)
            
        Raises:
            QueueNotFoundError: If queue not found
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(f"Queue '{queue_name}' not found")
            
            messages = self._messages[queue_name]
            
            # Remove expired messages
            self._messages[queue_name] = [m for m in messages if not m.is_expired()]
            messages = self._messages[queue_name]
            
            # Find visible messages
            visible_messages = []
            for message in messages:
                if message.is_visible() and len(visible_messages) < num_messages:
                    # Increment dequeue count
                    message.dequeue_count += 1
                    # Update visibility timeout and generate new pop receipt
                    message.update_visibility(visibility_timeout)
                    visible_messages.append(message)
            
            # Update queue message count
            self._queues[queue_name].properties.approximate_message_count = len(messages)
            
            return visible_messages
    
    async def peek_messages(
        self,
        queue_name: str,
        num_messages: int = 1,
    ) -> List[Message]:
        """
        Peek at messages without changing visibility.
        
        Args:
            queue_name: Queue name
            num_messages: Number of messages to peek (1-32)
            
        Returns:
            List of messages (may be fewer than requested)
            
        Raises:
            QueueNotFoundError: If queue not found
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(f"Queue '{queue_name}' not found")
            
            messages = self._messages[queue_name]
            
            # Remove expired messages
            self._messages[queue_name] = [m for m in messages if not m.is_expired()]
            messages = self._messages[queue_name]
            
            # Return visible messages without modifying them
            peeked = [m for m in messages if m.is_visible()][:num_messages]
            
            # Update queue message count
            self._queues[queue_name].properties.approximate_message_count = len(messages)
            
            return peeked
    
    async def update_message(
        self,
        queue_name: str,
        message_id: str,
        pop_receipt: str,
        visibility_timeout: int,
        message_text: Optional[str] = None,
    ) -> str:
        """
        Update a message's visibility timeout and optionally its content.
        
        Args:
            queue_name: Queue name
            message_id: Message ID
            pop_receipt: Pop receipt from get_messages
            visibility_timeout: New visibility timeout in seconds
            message_text: Optional new message text (base64-encoded)
            
        Returns:
            New pop receipt
            
        Raises:
            QueueNotFoundError: If queue not found
            MessageNotFoundError: If message not found
            InvalidPopReceiptError: If pop receipt is invalid
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(f"Queue '{queue_name}' not found")
            
            messages = self._messages[queue_name]
            
            # Find message
            message = None
            for m in messages:
                if m.message_id == message_id:
                    message = m
                    break
            
            if message is None:
                raise MessageNotFoundError(f"Message '{message_id}' not found")
            
            # Verify pop receipt
            if message.pop_receipt != pop_receipt:
                raise InvalidPopReceiptError("Invalid pop receipt")
            
            # Check if message is expired
            if message.is_expired():
                # Remove expired message
                self._messages[queue_name] = [m for m in messages if m.message_id != message_id]
                self._queues[queue_name].properties.approximate_message_count = len(self._messages[queue_name])
                raise MessageNotFoundError(f"Message '{message_id}' has expired")
            
            # Update message
            new_pop_receipt = message.update_visibility(visibility_timeout, message_text)
            
            return new_pop_receipt
    
    async def delete_message(
        self,
        queue_name: str,
        message_id: str,
        pop_receipt: str,
    ) -> None:
        """
        Delete a message from the queue.
        
        Args:
            queue_name: Queue name
            message_id: Message ID
            pop_receipt: Pop receipt from get_messages
            
        Raises:
            QueueNotFoundError: If queue not found
            MessageNotFoundError: If message not found
            InvalidPopReceiptError: If pop receipt is invalid
        """
        async with self._lock:
            if queue_name not in self._queues:
                raise QueueNotFoundError(f"Queue '{queue_name}' not found")
            
            messages = self._messages[queue_name]
            
            # Find message
            message = None
            for m in messages:
                if m.message_id == message_id:
                    message = m
                    break
            
            if message is None:
                raise MessageNotFoundError(f"Message '{message_id}' not found")
            
            # Verify pop receipt
            if message.pop_receipt != pop_receipt:
                raise InvalidPopReceiptError("Invalid pop receipt")
            
            # Remove message
            self._messages[queue_name] = [m for m in messages if m.message_id != message_id]
            
            # Update queue message count
            self._queues[queue_name].properties.approximate_message_count = len(self._messages[queue_name])
