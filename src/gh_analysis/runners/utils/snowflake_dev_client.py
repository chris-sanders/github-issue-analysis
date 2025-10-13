"""Snowflake client for dev database data storage and retrieval."""

import json
from typing import Any

from .snowflake_base import BaseSnowflakeClient


class SnowflakeDevClient(BaseSnowflakeClient):
    """Client for reading and writing experiment data to dev database."""

    def __init__(
        self,
        schema: str,
        account: str = None,
        user: str = None,
        private_key_path: str = None,
        private_key_passphrase: str = None,
        warehouse: str = None,
    ):
        """Initialize dev client - ALWAYS uses dev_cre database with required schema.

        Args:
            schema: Required schema name for the experiment (e.g. "EXP05", "EXP06")
            account: Snowflake account (from env if not provided)
            user: Snowflake user (from env if not provided)
            private_key_path: Path to private key (from env if not provided)
            private_key_passphrase: Private key passphrase (from env if not provided)
            warehouse: Snowflake warehouse (from env if not provided)
        """
        # HARDCODED: Always use dev_cre database for safety
        # Schema is required to ensure intentional experiment naming
        super().__init__(
            account=account,
            user=user,
            private_key_path=private_key_path,
            private_key_passphrase=private_key_passphrase,
            warehouse=warehouse,
            database="dev_cre",  # HARDCODED - never use env vars or parameters
            schema=schema,  # REQUIRED - forces intentional naming
        )

    def create_table(self, table_name: str, ddl: str) -> None:
        """Create a table if it doesn't exist.

        Args:
            table_name: Name of the table to create
            ddl: CREATE TABLE DDL statement
        """
        # Check if table exists - extract actual table name from fully qualified name
        actual_table_name = table_name.split(".")[-1]  # Get just the table name part
        check_query = f"""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = '{self.schema or "EXP05"}'
        AND TABLE_NAME = '{actual_table_name.upper()}'
        """

        results = self.execute_query(check_query)
        if results[0][0] == 0:
            print(f"Creating table {table_name}...")
            self.execute_non_query(ddl)
            print(f"✅ Table {table_name} created successfully")
        else:
            print(f"Table {table_name} already exists")

    def insert_data(self, table_name: str, data: list[dict[str, Any]]) -> int:
        """Insert data into a table.

        Args:
            table_name: Name of the table
            data: List of dictionaries with column names as keys

        Returns:
            Number of rows inserted
        """
        if not data:
            return 0

        # Get column names from first record
        columns = list(data[0].keys())
        ", ".join(columns)

        # Use custom method that handles arrays properly
        return self._insert_data_with_arrays(table_name, data)

    def _insert_data_with_arrays(
        self, table_name: str, data: list[dict[str, Any]]
    ) -> int:
        """Custom insert method that handles arrays properly using parameterized queries."""
        if not data:
            return 0

        # Get column names from first record
        columns = list(data[0].keys())
        column_list = ", ".join(columns)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                rows_inserted = 0
                for record in data:
                    # Build VALUES clause with parameterized array construction
                    value_parts = []
                    all_params = []

                    for col in columns:
                        value = record[col]
                        if isinstance(value, list):
                            # Build array using ARRAY_CONSTRUCT with parameters
                            if value:
                                placeholders = ", ".join(["%s"] * len(value))
                                array_literal = f"ARRAY_CONSTRUCT({placeholders})"
                                value_parts.append(array_literal)
                                all_params.extend(
                                    value
                                )  # Add array items as separate params
                            else:
                                value_parts.append("ARRAY_CONSTRUCT()")
                        else:
                            # Use parameter for non-array values
                            value_parts.append("%s")
                            all_params.append(value)

                    values_clause = ", ".join(value_parts)
                    query = f"INSERT INTO {table_name} ({column_list}) SELECT {values_clause}"

                    cursor.execute(query, all_params)
                    rows_inserted += cursor.rowcount

                return rows_inserted
            finally:
                cursor.close()

    def _format_value_for_snowflake(self, value: Any) -> Any:
        """Format a value for Snowflake insertion, handling arrays specially."""
        if isinstance(value, list):
            # Convert Python list to JSON string for PARSE_JSON
            return json.dumps(value)
        return value

    def upsert_data(
        self, table_name: str, data: list[dict[str, Any]], key_columns: list[str]
    ) -> int:
        """Insert or update data based on key columns.

        Args:
            table_name: Name of the table
            data: List of dictionaries with column names as keys
            key_columns: List of column names that form the unique key

        Returns:
            Number of rows affected
        """
        if not data:
            return 0

        # For now, use simple insert since MERGE with arrays is complex
        # In practice this is fine since we're upserting based on primary key
        # First delete existing records, then insert new ones

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Delete existing records matching the keys
                for record in data:
                    where_conditions = []
                    where_params = []
                    for key_col in key_columns:
                        where_conditions.append(f"{key_col} = %s")
                        where_params.append(record[key_col])

                    if where_conditions:
                        delete_query = f"DELETE FROM {table_name} WHERE {' AND '.join(where_conditions)}"
                        cursor.execute(delete_query, tuple(where_params))

                # Now insert the new data using the same connection
                if not data:
                    return 0

                # Use the same custom method for inserting with arrays
                for record in data:
                    # Build INSERT SELECT with proper array handling using parameters
                    columns = list(record.keys())
                    column_list = ", ".join(columns)

                    # Build VALUES clause with parameterized array construction
                    value_parts = []
                    all_params = []

                    for col in columns:
                        value = record[col]
                        if isinstance(value, list):
                            # Build array using ARRAY_CONSTRUCT with parameters
                            if value:
                                placeholders = ", ".join(["%s"] * len(value))
                                array_literal = f"ARRAY_CONSTRUCT({placeholders})"
                                value_parts.append(array_literal)
                                all_params.extend(
                                    value
                                )  # Add array items as separate params
                            else:
                                value_parts.append("ARRAY_CONSTRUCT()")
                        else:
                            # Use parameter for non-array values
                            value_parts.append("%s")
                            all_params.append(value)

                    values_clause = ", ".join(value_parts)
                    insert_query = f"INSERT INTO {table_name} ({column_list}) SELECT {values_clause}"

                    cursor.execute(insert_query, all_params)
                return cursor.rowcount

            finally:
                cursor.close()

    def fetch_data(
        self,
        table_name: str,
        where_clause: str = None,
        params: tuple = None,
    ) -> list[dict[str, Any]]:
        """Fetch data from a table and return as list of dictionaries.

        Args:
            table_name: Name of the table
            where_clause: Optional WHERE clause (without the WHERE keyword)
            params: Optional query parameters

        Returns:
            List of records as dictionaries
        """
        query = f"SELECT * FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                # Get column names
                columns = [desc[0] for desc in cursor.description]

                # Convert rows to dictionaries
                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))

                return results
            finally:
                cursor.close()

    def fetch_by_keys(
        self, table_name: str, key_values: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Fetch records by specific key combinations.

        Args:
            table_name: Name of the table
            key_values: List of dictionaries with key-value pairs to match
                       Example: [{"ORG_NAME": "org1", "REPO_NAME": "repo1", "ISSUE_NUMBER": 123}]

        Returns:
            List of matching records as dictionaries
        """
        if not key_values:
            return []

        # Build WHERE clause with OR conditions for each key combination
        conditions = []
        params = []

        for key_combo in key_values:
            key_conditions = []
            for key, value in key_combo.items():
                key_conditions.append(f"{key} = %s")
                params.append(value)
            conditions.append("(" + " AND ".join(key_conditions) + ")")

        where_clause = " OR ".join(conditions)
        return self.fetch_data(table_name, where_clause, tuple(params))
