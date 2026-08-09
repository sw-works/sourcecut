from __future__ import annotations

import os
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import cache

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

INSTRUMENTATION_NAME = "sourcecut"
SQL_STRING = re.compile(r"'(?:''|\\.|[^'])*'")
SQL_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
WHITESPACE = re.compile(r"\s+")
_configured = False


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of true/false, 1/0, yes/no, or on/off")


def configure_telemetry() -> bool:
    global _configured
    if _configured:
        return True
    if not _env_bool("SOURCECUT_TELEMETRY_ENABLED", False):
        return False
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint or "replace-" in endpoint:
        raise ValueError("OTEL_EXPORTER_OTLP_ENDPOINT must be configured when telemetry is enabled")
    headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    if not headers or "replace-" in headers:
        raise ValueError("OTEL_EXPORTER_OTLP_HEADERS must authenticate OTLP export")

    resource = Resource.create(
        {
            SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "sourcecut"),
            SERVICE_VERSION: "0.1.0",
            "deployment.environment.name": os.getenv(
                "OTEL_DEPLOYMENT_ENVIRONMENT", "development"
            ),
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    interval_ms = int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "10000"))
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(),
        export_interval_millis=interval_ms,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
    _configured = True
    return True


@contextmanager
def telemetry_span(
    name: str,
    attributes: Mapping[str, str | bool | int | float] | None = None,
    *,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Iterator[Span]:
    tracer = trace.get_tracer(INSTRUMENTATION_NAME)
    with tracer.start_as_current_span(name, attributes=attributes, kind=kind) as current:
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise


def record_completed_span(
    name: str,
    start_time_ns: int,
    end_time_ns: int,
    attributes: Mapping[str, str | bool | int | float],
    *,
    error_type: str | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> None:
    span = trace.get_tracer(INSTRUMENTATION_NAME).start_span(
        name,
        start_time=start_time_ns,
        attributes=attributes,
        kind=kind,
    )
    if error_type:
        span.set_attribute("error.type", error_type)
        span.set_status(Status(StatusCode.ERROR, error_type))
    span.end(end_time=end_time_ns)


@cache
def _counter(name: str):
    return metrics.get_meter(INSTRUMENTATION_NAME).create_counter(name)


@cache
def _histogram(name: str, unit: str):
    return metrics.get_meter(INSTRUMENTATION_NAME).create_histogram(name, unit=unit)


def add_counter(
    name: str,
    value: int,
    attributes: Mapping[str, str | bool | int | float] | None = None,
) -> None:
    _counter(name).add(value, attributes=attributes)


def observe_histogram(
    name: str,
    value: float,
    attributes: Mapping[str, str | bool | int | float] | None = None,
    *,
    unit: str = "ms",
) -> None:
    _histogram(name, unit).record(value, attributes=attributes)


def sanitize_sql(query: str) -> str:
    sanitized = SQL_STRING.sub("'?'", query)
    sanitized = SQL_NUMBER.sub("?", sanitized)
    return WHITESPACE.sub(" ", sanitized).strip().rstrip(";")[:4096]


def force_flush_telemetry(timeout_millis: int = 10_000) -> None:
    tracer_provider = trace.get_tracer_provider()
    meter_provider = metrics.get_meter_provider()
    if hasattr(tracer_provider, "force_flush"):
        tracer_provider.force_flush(timeout_millis=timeout_millis)
    if hasattr(meter_provider, "force_flush"):
        meter_provider.force_flush(timeout_millis=timeout_millis)
