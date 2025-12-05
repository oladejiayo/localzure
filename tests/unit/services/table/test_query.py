"""
Unit tests for OData query parser.

Tests filter expressions, comparison operators, logical operators,
string functions, and query parameter handling.
"""

import pytest
from datetime import datetime, timezone

from localzure.services.table.query import ODataFilter, ODataQuery, ODataParseError


class TestODataFilterComparison:
    """Tests for comparison operators."""
    
    def test_filter_eq(self):
        """Test equality operator."""
        filter_obj = ODataFilter("Name eq 'John'")
        
        assert filter_obj.evaluate({"Name": "John"}) is True
        assert filter_obj.evaluate({"Name": "Jane"}) is False
    
    def test_filter_ne(self):
        """Test not equal operator."""
        filter_obj = ODataFilter("Status ne 'inactive'")
        
        assert filter_obj.evaluate({"Status": "active"}) is True
        assert filter_obj.evaluate({"Status": "inactive"}) is False
    
    def test_filter_gt(self):
        """Test greater than operator."""
        filter_obj = ODataFilter("Age gt 30")
        
        assert filter_obj.evaluate({"Age": 35}) is True
        assert filter_obj.evaluate({"Age": 30}) is False
        assert filter_obj.evaluate({"Age": 25}) is False
    
    def test_filter_ge(self):
        """Test greater than or equal operator."""
        filter_obj = ODataFilter("Price ge 100")
        
        assert filter_obj.evaluate({"Price": 150}) is True
        assert filter_obj.evaluate({"Price": 100}) is True
        assert filter_obj.evaluate({"Price": 50}) is False
    
    def test_filter_lt(self):
        """Test less than operator."""
        filter_obj = ODataFilter("Score lt 50")
        
        assert filter_obj.evaluate({"Score": 30}) is True
        assert filter_obj.evaluate({"Score": 50}) is False
        assert filter_obj.evaluate({"Score": 70}) is False
    
    def test_filter_le(self):
        """Test less than or equal operator."""
        filter_obj = ODataFilter("Count le 10")
        
        assert filter_obj.evaluate({"Count": 5}) is True
        assert filter_obj.evaluate({"Count": 10}) is True
        assert filter_obj.evaluate({"Count": 15}) is False
    
    def test_filter_with_numbers(self):
        """Test filtering with integer and float values."""
        filter_int = ODataFilter("Value eq 42")
        filter_float = ODataFilter("Price eq 19.99")
        
        assert filter_int.evaluate({"Value": 42}) is True
        assert filter_float.evaluate({"Price": 19.99}) is True
    
    def test_filter_with_boolean(self):
        """Test filtering with boolean values."""
        filter_obj = ODataFilter("IsActive eq true")
        
        assert filter_obj.evaluate({"IsActive": True}) is True
        assert filter_obj.evaluate({"IsActive": False}) is False


class TestODataFilterLogical:
    """Tests for logical operators."""
    
    def test_filter_and(self):
        """Test AND operator."""
        filter_obj = ODataFilter("Age gt 25 and Status eq 'active'")
        
        assert filter_obj.evaluate({"Age": 30, "Status": "active"}) is True
        assert filter_obj.evaluate({"Age": 20, "Status": "active"}) is False
        assert filter_obj.evaluate({"Age": 30, "Status": "inactive"}) is False
        assert filter_obj.evaluate({"Age": 20, "Status": "inactive"}) is False
    
    def test_filter_or(self):
        """Test OR operator."""
        filter_obj = ODataFilter("Priority eq 'high' or Priority eq 'urgent'")
        
        assert filter_obj.evaluate({"Priority": "high"}) is True
        assert filter_obj.evaluate({"Priority": "urgent"}) is True
        assert filter_obj.evaluate({"Priority": "low"}) is False
    
    def test_filter_not(self):
        """Test NOT operator."""
        filter_obj = ODataFilter("not Status eq 'deleted'")
        
        assert filter_obj.evaluate({"Status": "active"}) is True
        assert filter_obj.evaluate({"Status": "deleted"}) is False
    
    def test_filter_complex_and_or(self):
        """Test complex AND/OR combination."""
        filter_obj = ODataFilter("Category eq 'A' and Price gt 50 or Priority eq 'high'")
        
        # (Category eq 'A' and Price gt 50) or (Priority eq 'high')
        assert filter_obj.evaluate({"Category": "A", "Price": 100, "Priority": "low"}) is True
        assert filter_obj.evaluate({"Category": "B", "Price": 100, "Priority": "high"}) is True
        assert filter_obj.evaluate({"Category": "B", "Price": 100, "Priority": "low"}) is False
    
    def test_filter_parentheses(self):
        """Test parentheses for grouping."""
        filter_obj = ODataFilter("(Age gt 25 or Age lt 18) and Status eq 'active'")
        
        assert filter_obj.evaluate({"Age": 30, "Status": "active"}) is True
        assert filter_obj.evaluate({"Age": 15, "Status": "active"}) is True
        assert filter_obj.evaluate({"Age": 20, "Status": "active"}) is False


class TestODataFilterStringFunctions:
    """Tests for string functions."""
    
    def test_filter_startswith(self):
        """Test startswith function."""
        filter_obj = ODataFilter("startswith(Name, 'John')")
        
        assert filter_obj.evaluate({"Name": "John Doe"}) is True
        assert filter_obj.evaluate({"Name": "Jane Doe"}) is False
    
    def test_filter_endswith(self):
        """Test endswith function."""
        filter_obj = ODataFilter("endswith(Email, '@example.com')")
        
        assert filter_obj.evaluate({"Email": "user@example.com"}) is True
        assert filter_obj.evaluate({"Email": "user@other.com"}) is False
    
    def test_filter_contains(self):
        """Test contains function."""
        filter_obj = ODataFilter("contains(Description, 'azure')")
        
        assert filter_obj.evaluate({"Description": "This is azure storage"}) is True
        assert filter_obj.evaluate({"Description": "This is AWS storage"}) is False
    
    def test_string_functions_with_logical(self):
        """Test string functions combined with logical operators."""
        filter_obj = ODataFilter("startswith(Name, 'A') and contains(City, 'New')")
        
        assert filter_obj.evaluate({"Name": "Alice", "City": "New York"}) is True
        assert filter_obj.evaluate({"Name": "Bob", "City": "New York"}) is False


class TestODataFilterEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_filter(self):
        """Test empty filter expression."""
        filter_obj = ODataFilter("")
        
        assert filter_obj.evaluate({"Name": "Test"}) is True
    
    def test_missing_property(self):
        """Test filtering on non-existent property."""
        filter_obj = ODataFilter("NonExistent eq 'value'")
        
        # Should return False when property doesn't exist
        assert filter_obj.evaluate({"Name": "Test"}) is False
    
    def test_type_mismatch(self):
        """Test comparison with mismatched types."""
        filter_obj = ODataFilter("Age gt 'thirty'")
        
        # Should handle type mismatch gracefully
        assert filter_obj.evaluate({"Age": 30}) is False
    
    def test_case_insensitive_operators(self):
        """Test that operators are case-insensitive."""
        filter_upper = ODataFilter("Name EQ 'John'")
        filter_lower = ODataFilter("Name eq 'John'")  # Property name should match case
        filter_mixed = ODataFilter("Name Eq 'John'")
        
        entity = {"Name": "John"}
        assert filter_upper.evaluate(entity) is True
        assert filter_lower.evaluate(entity) is True
        assert filter_mixed.evaluate(entity) is True
    
    def test_invalid_operator(self):
        """Test invalid operator raises error."""
        filter_obj = ODataFilter("Age invalid 30")
        
        with pytest.raises(ODataParseError):
            filter_obj.parse()
    
    def test_incomplete_expression(self):
        """Test incomplete expression raises error."""
        filter_obj = ODataFilter("Age gt")
        
        with pytest.raises(ODataParseError):
            filter_obj.parse()
    
    def test_missing_closing_parenthesis(self):
        """Test missing closing parenthesis raises error."""
        filter_obj = ODataFilter("(Age gt 30 and Status eq 'active'")
        
        with pytest.raises(ODataParseError):
            filter_obj.parse()


class TestODataFilterMultipleConditions:
    """Tests for complex filter combinations."""
    
    def test_three_way_and(self):
        """Test three conditions with AND."""
        filter_obj = ODataFilter("Category eq 'A' and Price gt 50 and Stock lt 100")
        
        assert filter_obj.evaluate({"Category": "A", "Price": 75, "Stock": 50}) is True
        assert filter_obj.evaluate({"Category": "B", "Price": 75, "Stock": 50}) is False
    
    def test_three_way_or(self):
        """Test three conditions with OR."""
        filter_obj = ODataFilter("Status eq 'pending' or Status eq 'active' or Status eq 'processing'")
        
        assert filter_obj.evaluate({"Status": "pending"}) is True
        assert filter_obj.evaluate({"Status": "active"}) is True
        assert filter_obj.evaluate({"Status": "completed"}) is False
    
    def test_mixed_and_or_precedence(self):
        """Test AND has higher precedence than OR."""
        # A and B or C = (A and B) or C
        filter_obj = ODataFilter("Type eq 'premium' and Price gt 100 or Featured eq true")
        
        assert filter_obj.evaluate({"Type": "premium", "Price": 150, "Featured": False}) is True
        assert filter_obj.evaluate({"Type": "basic", "Price": 150, "Featured": True}) is True
        assert filter_obj.evaluate({"Type": "basic", "Price": 150, "Featured": False}) is False


class TestODataQuery:
    """Tests for ODataQuery class."""
    
    def test_query_with_filter(self):
        """Test query with filter only."""
        query = ODataQuery(filter_expr="Age gt 30")
        
        assert query.matches({"Age": 35}) is True
        assert query.matches({"Age": 25}) is False
    
    def test_query_without_filter(self):
        """Test query without filter matches all."""
        query = ODataQuery()
        
        assert query.matches({"Age": 35}) is True
        assert query.matches({"Name": "Test"}) is True
    
    def test_query_with_select(self):
        """Test $select projects properties."""
        query = ODataQuery(select="Name,Age")
        
        entity = {
            "PartitionKey": "pk1",
            "RowKey": "rk1",
            "Name": "John",
            "Age": 30,
            "City": "Seattle"
        }
        
        projected = query.project(entity)
        
        # System properties always included
        assert "PartitionKey" in projected
        assert "RowKey" in projected
        # Selected properties included
        assert "Name" in projected
        assert "Age" in projected
        # Non-selected properties excluded
        assert "City" not in projected
    
    def test_query_without_select(self):
        """Test no $select returns all properties."""
        query = ODataQuery()
        
        entity = {"Name": "John", "Age": 30, "City": "Seattle"}
        projected = query.project(entity)
        
        assert projected == entity
    
    def test_query_with_top(self):
        """Test $top parameter is stored."""
        query = ODataQuery(top=50)
        
        assert query.top == 50
    
    def test_query_combined_parameters(self):
        """Test query with filter, select, and top."""
        query = ODataQuery(
            filter_expr="Age gt 25",
            select="Name,Email",
            top=10
        )
        
        entity = {
            "PartitionKey": "pk1",
            "RowKey": "rk1",
            "Name": "John",
            "Age": 30,
            "Email": "john@example.com",
            "City": "Seattle"
        }
        
        assert query.matches(entity) is True
        
        projected = query.project(entity)
        assert "Name" in projected
        assert "Email" in projected
        assert "City" not in projected
        
        assert query.top == 10
