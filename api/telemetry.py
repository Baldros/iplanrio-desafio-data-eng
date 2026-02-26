"""
Módulo de Observabilidade — OpenTelemetry

Configura tracing distribuído para a API REST.
A ativação é condicional: só instrumenta se OTEL_ENABLED=true.

Arquitetura:
    FastAPI (auto-instrument) ──OTLP──→ Jaeger (visualização de traces)
"""

from config import settings


def setup_telemetry(app):
    """
    Configura OpenTelemetry na aplicação FastAPI.
    Se OTEL_ENABLED estiver desabilitado, não faz nada.
    
    :param app: Instância do FastAPI.
    :returns: TracerProvider configurado ou None.
    """
    if not settings.OTEL_ENABLED:
        return None
    
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    # Identifica o serviço nos traces
    resource = Resource.create({
        "service.name": settings.OTEL_SERVICE_NAME,
        "service.version": "1.0.0",
    })

    # Configura o provedor de traces
    provider = TracerProvider(resource=resource)
    
    # Exportador OTLP via HTTP para o Jaeger
    exporter = OTLPSpanExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces"
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    
    trace.set_tracer_provider(provider)

    # Auto-instrumentação do FastAPI
    # Todas as rotas passam a gerar spans automaticamente
    FastAPIInstrumentor.instrument_app(app)

    return provider


def shutdown_telemetry(provider):
    """
    Encerra o TracerProvider, fazendo flush dos spans pendentes.
    """
    if provider:
        provider.shutdown()
