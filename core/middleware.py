import logging
import time

from django.conf import settings
from django.db import connection


logger = logging.getLogger("bioattend.performance")


class RequestTimingMiddleware:
    """Log request duration and database query count when explicitly enabled."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.log_enabled = getattr(settings, "REQUEST_TIMING_LOG", False)
        self.headers_enabled = getattr(settings, "REQUEST_TIMING_HEADERS", True)

    def __call__(self, request):
        if not self.log_enabled and not self.headers_enabled:
            return self.get_response(request)

        query_count = 0
        query_duration = 0.0

        def count_queries(execute, sql, params, many, context):
            nonlocal query_count, query_duration
            query_count += 1
            started_at = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                query_duration += time.perf_counter() - started_at

        started_at = time.perf_counter()
        with connection.execute_wrapper(count_queries):
            response = self.get_response(request)
        total_duration = time.perf_counter() - started_at

        total_ms = total_duration * 1000
        db_ms = query_duration * 1000

        if self.headers_enabled:
            response["X-BioAttend-Duration-ms"] = f"{total_ms:.1f}"
            response["X-BioAttend-DB-Queries"] = str(query_count)
            response["X-BioAttend-DB-ms"] = f"{db_ms:.1f}"

        if self.log_enabled:
            logger.info(
                "request path=%s method=%s status=%s duration_ms=%.1f db_queries=%s db_ms=%.1f",
                request.get_full_path(),
                request.method,
                getattr(response, "status_code", "-"),
                total_ms,
                query_count,
                db_ms,
            )
        return response
