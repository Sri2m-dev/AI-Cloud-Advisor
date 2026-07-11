"""Supabase client abstraction for Data Fabric repository adapters."""

from __future__ import annotations

from time import sleep
from typing import Any, Callable, Protocol

from data_fabric.adapters.supabase.config import DataFabricDatabaseConfig
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterOperationError


class SupabaseTableOperation(Protocol):
    def select(self, columns: str = "*") -> Any: ...
    def insert(self, payload: dict[str, Any]) -> Any: ...
    def update(self, payload: dict[str, Any]) -> Any: ...
    def eq(self, column: str, value: Any) -> Any: ...
    def order(self, column: str, desc: bool = False) -> Any: ...
    def range(self, start: int, end: int) -> Any: ...
    def limit(self, count: int) -> Any: ...
    def execute(self) -> Any: ...


class SupabaseDataFabricClient:
    """Server-side Supabase client wrapper with retry/error normalization."""

    def __init__(self, config: DataFabricDatabaseConfig, raw_client: Any | None = None) -> None:
        self.config = config
        self._raw_client = raw_client

    @property
    def raw_client(self) -> Any:
        if self._raw_client is None:
            try:
                from supabase import create_client  # type: ignore
            except Exception as exc:  # pragma: no cover - exercised only when dependency absent
                raise SupabaseAdapterOperationError("Supabase package is not available") from exc
            self._raw_client = create_client(self.config.supabase_url, self.config.service_role_key)
        return self._raw_client

    def table(self, table_name: str) -> SupabaseTableOperation:
        qualified = f"{self.config.schema_name}.{table_name}"
        return self.raw_client.table(qualified)

    def rpc(self, function_name: str, params: dict[str, Any]) -> Any:
        return self.raw_client.rpc(function_name, params).execute()

    def execute(self, operation: Callable[[], Any]) -> Any:
        attempts = self.config.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = operation()
                error = getattr(response, "error", None)
                if error:
                    raise SupabaseAdapterOperationError(str(error))
                return response
            except SupabaseAdapterOperationError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    break
                sleep(self.config.retry_backoff_seconds)
        raise self.normalize_error(last_error)

    def normalize_error(self, error: Exception | None) -> SupabaseAdapterOperationError:
        message = "Supabase operation failed" if error is None else str(error)
        return SupabaseAdapterOperationError(message)

    def health_check(self) -> bool:
        if not self.config.enable_health_check:
            return True
        response = self.execute(lambda: self.table("enterprise_entities").select("id").limit(1).execute())
        return getattr(response, "data", None) is not None

