"""
Supabase database connector module.

This module provides a connector class for interacting with Supabase database.
"""

import os
from typing import Any

from supabase import create_client, Client


class SupabaseConnector:
    """
    A connector class for Supabase database operations.

    This class provides methods for CRUD operations on Supabase tables.
    """

    def __init__(self, url: str | None = None, key: str | None = None):
        """
        Initialize the Supabase connector.

        Args:
            url: Supabase project URL. If not provided, reads from SUPABASE_URL env var.
            key: Supabase API key. If not provided, reads from SUPABASE_KEY env var.

        Raises:
            ValueError: If URL or key is not provided and not found in environment.
        """
        self.url = url or os.environ.get("SUPABASE_URL")
        self.key = key or os.environ.get("SUPABASE_KEY")

        if not self.url:
            raise ValueError("SUPABASE_URL is required. Set it as environment variable or pass it directly.")
        if not self.key:
            raise ValueError("SUPABASE_KEY is required. Set it as environment variable or pass it directly.")

        self._client: Client = create_client(self.url, self.key)

    @property
    def client(self) -> Client:
        """Get the underlying Supabase client."""
        return self._client

    def insert(self, table: str, data: dict[str, Any] | list[dict[str, Any]]) -> dict:
        """
        Insert data into a table.

        Args:
            table: The table name.
            data: A dictionary or list of dictionaries containing the data to insert.

        Returns:
            The response data from Supabase.
        """
        response = self._client.table(table).insert(data).execute()
        return response.data

    def select(
        self,
        table: str,
        columns: str = "*",
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        ascending: bool = True
    ) -> list[dict]:
        """
        Select data from a table.

        Args:
            table: The table name.
            columns: Columns to select (default "*" for all).
            filters: Dictionary of column-value pairs for filtering (uses eq).
            limit: Maximum number of rows to return.
            order_by: Column name to order by.
            ascending: Sort order (default True for ascending).

        Returns:
            A list of matching records.
        """
        query = self._client.table(table).select(columns)

        if filters:
            for column, value in filters.items():
                query = query.eq(column, value)

        if order_by:
            query = query.order(order_by, desc=not ascending)

        if limit:
            query = query.limit(limit)

        response = query.execute()
        return response.data

    def update(self, table: str, data: dict[str, Any], filters: dict[str, Any]) -> list[dict]:
        """
        Update data in a table.

        Args:
            table: The table name.
            data: Dictionary of column-value pairs to update.
            filters: Dictionary of column-value pairs for filtering (uses eq).

        Returns:
            A list of updated records.
        """
        query = self._client.table(table).update(data)

        for column, value in filters.items():
            query = query.eq(column, value)

        response = query.execute()
        return response.data

    def delete(self, table: str, filters: dict[str, Any]) -> list[dict]:
        """
        Delete data from a table.

        Args:
            table: The table name.
            filters: Dictionary of column-value pairs for filtering (uses eq).

        Returns:
            A list of deleted records.
        """
        query = self._client.table(table).delete()

        for column, value in filters.items():
            query = query.eq(column, value)

        response = query.execute()
        return response.data

    def upsert(self, table: str, data: dict[str, Any] | list[dict[str, Any]]) -> list[dict]:
        """
        Upsert data into a table (insert or update if exists).

        Args:
            table: The table name.
            data: A dictionary or list of dictionaries containing the data.

        Returns:
            A list of upserted records.
        """
        response = self._client.table(table).upsert(data).execute()
        return response.data

    def count(self, table: str, filters: dict[str, Any] | None = None) -> int:
        """
        Count records in a table.

        Args:
            table: The table name.
            filters: Optional dictionary of column-value pairs for filtering.

        Returns:
            The count of matching records.
        """
        query = self._client.table(table).select("*", count="exact")

        if filters:
            for column, value in filters.items():
                query = query.eq(column, value)

        response = query.execute()
        return response.count or 0
