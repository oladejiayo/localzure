"""
Azure Table Storage Service emulator.

This module provides an in-memory implementation of Azure Table Storage
with support for table and entity CRUD operations and OData queries.
"""

from localzure.services.table.models import (
    Table,
    Entity,
    InsertEntityRequest,
    UpdateEntityRequest,
    MergeEntityRequest,
)
from localzure.services.table.backend import TableBackend, backend
from localzure.services.table.query import ODataQuery, ODataFilter, ODataParseError

__all__ = [
    "Table",
    "Entity",
    "InsertEntityRequest",
    "UpdateEntityRequest",
    "MergeEntityRequest",
    "TableBackend",
    "backend",
    "ODataQuery",
    "ODataFilter",
    "ODataParseError",
]
