"""Base Snowflake client with common connection and query functionality."""

import os
from abc import ABC
from pathlib import Path

import snowflake.connector
from cryptography.hazmat.primitives import serialization


class BaseSnowflakeClient(ABC):
    """Base class for Snowflake clients with common connection logic."""

    def __init__(
        self,
        account: str | None = None,
        user: str | None = None,
        private_key_path: str | None = None,
        private_key_passphrase: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
    ):
        """Initialize with Snowflake connection parameters."""
        self.account = account or os.getenv("SNOWFLAKE_ACCOUNT")
        self.user = user or os.getenv("SNOWFLAKE_USER")
        self.private_key_path = private_key_path or os.getenv(
            "SNOWFLAKE_PRIVATE_KEY_PATH"
        )
        self.private_key_passphrase = private_key_passphrase or os.getenv(
            "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"
        )
        self.warehouse = warehouse or os.getenv("SNOWFLAKE_WAREHOUSE")
        # Database and schema are now set by subclasses, not from environment
        self.database = database
        self.schema = schema

        # Validate required parameters
        if not all([self.account, self.user, self.private_key_path]):
            raise ValueError(
                "Snowflake account, user, and private_key_path are required"
            )

    def _load_private_key(self):
        """Load and return the private key for authentication."""
        private_key_path = Path(self.private_key_path).expanduser()
        if not private_key_path.exists():
            raise ValueError(f"Private key file not found: {private_key_path}")

        with open(private_key_path, "rb") as key_file:
            private_key_data = key_file.read()

        # Load private key with optional passphrase
        passphrase = (
            self.private_key_passphrase.encode()
            if self.private_key_passphrase
            else None
        )
        private_key = serialization.load_pem_private_key(
            private_key_data,
            password=passphrase,
        )

        return private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    def _get_connection(self):
        """Get Snowflake connection using key pair authentication."""
        return snowflake.connector.connect(
            account=self.account,
            user=self.user,
            private_key=self._load_private_key(),
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema,
        )

    def execute_query(self, query: str, params: tuple | None = None) -> list[tuple]:
        """Execute a SQL query and return results.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            List of result rows as tuples
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return cursor.fetchall()
            finally:
                cursor.close()

    def execute_non_query(self, query: str, params: tuple | None = None) -> int:
        """Execute a SQL query that doesn't return results (INSERT, UPDATE, CREATE, etc.).

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            Number of rows affected
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return cursor.rowcount
            finally:
                cursor.close()
