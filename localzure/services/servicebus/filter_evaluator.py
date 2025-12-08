"""
Service Bus SQL Filter Evaluator

Helper module for evaluating SQL filter expressions against messages.

Author: Ayodele Oladeji
Date: 2025-12-05
"""

from typing import Any, Dict, Optional

from .models import ServiceBusMessage, SubscriptionFilter


class SqlFilterEvaluator:
    """
    Evaluates SQL filter expressions against Service Bus messages.
    
    Supports basic SQL92 subset including:
    - Property comparisons: sys.Label = 'value', quantity > 100
    - Logical operators: AND, OR
    - IN operator: color IN ('red', 'blue')
    - Comparison operators: =, !=, <>, <, >, <=, >=
    """
    
    def evaluate(
        self,
        filter_obj: SubscriptionFilter,
        message: ServiceBusMessage
    ) -> bool:
        """
        Evaluate SQL filter expression against a message.
        
        Args:
            filter_obj: SQL filter to evaluate
            message: Message to evaluate against
            
        Returns:
            True if message matches filter, False otherwise
        """
        if not filter_obj.sql_expression:
            return True
        
        expression = filter_obj.sql_expression.strip()
        context = self._build_context(message)
        
        try:
            return self._evaluate_expression(expression, context)
        except Exception:
            # If evaluation fails, don't match
            return False
    
    def _build_context(self, message: ServiceBusMessage) -> Dict[str, Any]:
        """
        Build evaluation context from message properties.
        
        Args:
            message: Message to extract properties from
            
        Returns:
            Dictionary of property values for evaluation
        """
        context = {
            'sys': {
                'Label': message.label,
                'MessageId': message.message_id,
                'ContentType': message.content_type,
                'CorrelationId': message.correlation_id,
                'To': message.to,
                'ReplyTo': message.reply_to,
                'SessionId': message.session_id,
            }
        }
        
        # Add user properties
        if message.user_properties:
            context.update(message.user_properties)
        
        return context
    
    def _evaluate_expression(
        self,
        expression: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Recursively evaluate a SQL filter expression.
        
        Args:
            expression: SQL expression to evaluate
            context: Property values
            
        Returns:
            Boolean result of evaluation
        """
        expression = expression.strip()
        
        # Handle OR operator (lowest precedence)
        if ' OR ' in expression.upper():
            return self._evaluate_logical_or(expression, context)
        
        # Handle AND operator
        if ' AND ' in expression.upper():
            return self._evaluate_logical_and(expression, context)
        
        # Handle IN operator
        if ' IN ' in expression.upper():
            return self._evaluate_in_operator(expression, context)
        
        # Handle comparison operators
        for operator in ['>=', '<=', '<>', '!=', '=', '<', '>']:
            if operator in expression:
                return self._evaluate_comparison(expression, operator, context)
        
        return False
    
    def _evaluate_logical_or(
        self,
        expression: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate OR logical operator.
        
        Args:
            expression: Expression containing OR
            context: Property values
            
        Returns:
            True if any operand is true
        """
        parts = expression.split(' OR ', 1)
        left = self._evaluate_expression(parts[0].strip(), context)
        right = self._evaluate_expression(parts[1].strip(), context)
        return left or right
    
    def _evaluate_logical_and(
        self,
        expression: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate AND logical operator.
        
        Args:
            expression: Expression containing AND
            context: Property values
            
        Returns:
            True if all operands are true
        """
        parts = expression.split(' AND ', 1)
        left = self._evaluate_expression(parts[0].strip(), context)
        right = self._evaluate_expression(parts[1].strip(), context)
        return left and right
    
    def _evaluate_in_operator(
        self,
        expression: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate IN operator (e.g., color IN ('red', 'blue')).
        
        Args:
            expression: Expression containing IN
            context: Property values
            
        Returns:
            True if property value is in the list
        """
        in_pos = expression.upper().find(' IN ')
        if in_pos == -1:
            return False
        
        property_name = expression[:in_pos].strip()
        values_str = expression[in_pos + 4:].strip()
        
        # Extract values from parentheses
        if not (values_str.startswith('(') and values_str.endswith(')')):
            return False
        
        values_str = values_str[1:-1]  # Remove parentheses
        values = [v.strip().strip("'\"") for v in values_str.split(',')]
        
        # Get property value
        prop_value = self._get_property_value(property_name, context)
        if prop_value is None:
            return False
        
        return str(prop_value) in values
    
    def _evaluate_comparison(
        self,
        expression: str,
        operator: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate comparison operator.
        
        Args:
            expression: Expression containing comparison
            operator: Comparison operator (=, !=, <, >, etc.)
            context: Property values
            
        Returns:
            Result of comparison
        """
        parts = expression.split(operator, 1)
        if len(parts) != 2:
            return False
        
        left = parts[0].strip()
        right = parts[1].strip().strip("'\"")
        
        # Get property value
        left_value = self._get_property_value(left, context)
        if left_value is None:
            return False
        
        # Perform comparison
        return self._compare_values(left_value, operator, right)
    
    def _get_property_value(
        self,
        property_name: str,
        context: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Get property value from context.
        
        Supports nested properties like 'sys.Label'.
        
        Args:
            property_name: Name of property (may be dotted)
            context: Property values
            
        Returns:
            Property value or None if not found
        """
        parts = property_name.split('.')
        value = context
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        
        return value
    
    def _compare_values(
        self,
        left: Any,
        operator: str,
        right: Any
    ) -> bool:
        """
        Compare two values using the specified operator.
        
        Args:
            left: Left operand
            operator: Comparison operator
            right: Right operand (as string)
            
        Returns:
            Result of comparison
        """
        # Try numeric comparison first
        try:
            left_num = float(left) if not isinstance(left, bool) else left
            right_num = float(right)
            
            if operator in ('=', '=='):
                return left_num == right_num
            elif operator in ('!=', '<>'):
                return left_num != right_num
            elif operator == '<':
                return left_num < right_num
            elif operator == '>':
                return left_num > right_num
            elif operator == '<=':
                return left_num <= right_num
            elif operator == '>=':
                return left_num >= right_num
        except (ValueError, TypeError):
            pass
        
        # Fall back to string comparison
        left_str = str(left) if left is not None else ''
        right_str = str(right)
        
        if operator in ('=', '=='):
            return left_str == right_str
        elif operator in ('!=', '<>'):
            return left_str != right_str
        elif operator == '<':
            return left_str < right_str
        elif operator == '>':
            return left_str > right_str
        elif operator == '<=':
            return left_str <= right_str
        elif operator == '>=':
            return left_str >= right_str
        
        return False
