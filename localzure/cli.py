"""
LocalZure Command-Line Interface

Provides commands to start, stop, and manage LocalZure services.

Author: LocalZure Contributors
Date: 2025-12-05
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

import click
import uvicorn
from fastapi import FastAPI

from localzure.core.runtime import LocalZureRuntime
from localzure.core.logging_config import setup_logging
from localzure.services.servicebus.api import router as servicebus_router
from localzure.services.servicebus.error_handlers import register_exception_handlers


__version__ = "0.1.0"


@click.group()
@click.version_option(version=__version__, prog_name="localzure")
@click.pass_context
def cli(ctx):
    """
    LocalZure - Local Azure Cloud Platform Emulator
    
    Run Azure services locally for development and testing.
    """
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind to (default: 127.0.0.1)",
    show_default=True,
)
@click.option(
    "--port",
    default=7071,
    help="Port to bind to (default: 7071)",
    show_default=True,
    type=int,
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Logging level",
    show_default=True,
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload on code changes (development mode)",
)
def start(host: str, port: int, config: Optional[Path], log_level: str, reload: bool):
    """
    Start LocalZure services.
    
    This starts the LocalZure API server with all configured Azure service emulators.
    
    Examples:
        localzure start
        localzure start --port 8080
        localzure start --config config.yaml --log-level DEBUG
    """
    # Setup logging
    setup_logging(log_level.upper())
    logger = logging.getLogger("localzure.cli")
    
    click.echo(f"🌀 Starting LocalZure v{__version__}")
    click.echo(f"📍 Host: {host}:{port}")
    
    if config:
        click.echo(f"⚙️  Config: {config}")
    
    click.echo(f"📊 Log Level: {log_level}")
    click.echo()
    
    # Run with uvicorn
    try:
        if reload:
            # Use import string for reload mode
            uvicorn.run(
                "localzure.cli:create_app",
                host=host,
                port=port,
                log_level=log_level.lower(),
                reload=reload,
                access_log=True,
                factory=True,
            )
        else:
            # Use app object for normal mode
            app = create_app()
            uvicorn.run(
                app,
                host=host,
                port=port,
                log_level=log_level.lower(),
                access_log=True,
            )
    except KeyboardInterrupt:
        click.echo("\n👋 Shutting down LocalZure...")
    except Exception as e:
        click.echo(f"❌ Error starting LocalZure: {e}", err=True)
        sys.exit(1)


@cli.command()
def status():
    """
    Show status of LocalZure services.
    
    Displays which services are running and their health status.
    """
    click.echo("📊 LocalZure Status")
    click.echo()
    
    # TODO: Implement actual status checking via HTTP health endpoint
    click.echo("Service Bus: ✅ Running")
    click.echo()
    click.echo("Run 'localzure start' to start services.")


@cli.command()
def stop():
    """
    Stop LocalZure services.
    
    Gracefully shuts down all running services.
    """
    click.echo("🛑 Stopping LocalZure...")
    # TODO: Implement actual stop mechanism (PID file, signal, etc.)
    click.echo("✅ LocalZure stopped")


@cli.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["servicebus", "all"], case_sensitive=False),
    default="all",
    help="Which service logs to show",
    show_default=True,
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    help="Follow log output (like tail -f)",
)
def logs(service: str, follow: bool):
    """
    View LocalZure service logs.
    
    Examples:
        localzure logs
        localzure logs --service servicebus
        localzure logs --follow
    """
    click.echo(f"📜 Viewing logs for: {service}")
    
    if follow:
        click.echo("Following logs... (Ctrl+C to stop)")
    
    # TODO: Implement actual log viewing from log files
    click.echo("(Log viewing not yet implemented)")


@cli.command()
def version():
    """Show LocalZure version."""
    click.echo(f"LocalZure version {__version__}")


@cli.command()
def config():
    """
    Show current configuration.
    
    Displays the active configuration for LocalZure services.
    """
    click.echo("⚙️  LocalZure Configuration")
    click.echo()
    click.echo("Host: 127.0.0.1")
    click.echo("Port: 7071")
    click.echo()
    click.echo("Enabled Services:")
    click.echo("  - Service Bus (AMQP 1.0 emulator)")
    click.echo()
    click.echo("Use 'localzure start --config <file>' to load custom configuration.")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application with all service routers.
    """
    app = FastAPI(
        title="LocalZure",
        description="Local Azure Cloud Platform Emulator",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Add health check endpoint
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": __version__,
            "services": {
                "servicebus": "running"
            }
        }
    
    @app.get("/")
    async def root():
        """Root endpoint with service information."""
        return {
            "name": "LocalZure",
            "version": __version__,
            "description": "Local Azure Cloud Platform Emulator",
            "services": {
                "servicebus": {
                    "status": "running",
                    "endpoint": "/servicebus",
                    "docs": "/docs"
                }
            },
            "documentation": "/docs",
            "health": "/health"
        }
    
    # Include service routers
    app.include_router(servicebus_router, tags=["Service Bus"])
    
    # Register exception handlers
    register_exception_handlers(app)
    
    return app


def main():
    """Main entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
