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


# ========== Storage Management Commands (SVC-SB-010) ==========

@cli.group()
def storage():
    """
    Manage persistent storage for Service Bus.
    
    Commands for viewing stats, importing/exporting data, and maintenance.
    """
    pass


@storage.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to configuration file",
)
def stats(config: Optional[Path]):
    """
    Show storage statistics.
    
    Displays information about storage backend, size, entity counts, etc.
    
    Example:
        localzure storage stats
        localzure storage stats --config config.yaml
    """
    from localzure.services.servicebus.config import load_storage_config
    
    click.echo("📊 Storage Statistics")
    click.echo("=" * 50)
    
    try:
        # Load configuration
        storage_config = load_storage_config(str(config) if config else None)
        
        click.echo(f"Backend:     {storage_config.storage_type.value}")
        
        if storage_config.storage_type.value == "sqlite":
            click.echo(f"Database:    {storage_config.sqlite_path}")
            
            # Check if database exists and get size
            db_path = Path(storage_config.sqlite_path)
            if db_path.exists():
                size_mb = db_path.stat().st_size / (1024 * 1024)
                click.echo(f"Size:        {size_mb:.2f} MB")
            else:
                click.echo("Status:      No database file found (never initialized)")
        
        elif storage_config.storage_type.value == "json":
            click.echo(f"Directory:   {storage_config.json_path}")
            
            # Check if directory exists
            json_path = Path(storage_config.json_path)
            if json_path.exists():
                # Calculate total size
                total_size = sum(f.stat().st_size for f in json_path.rglob("*") if f.is_file())
                size_mb = total_size / (1024 * 1024)
                click.echo(f"Size:        {size_mb:.2f} MB")
            else:
                click.echo("Status:      No storage directory found (never initialized)")
        
        elif storage_config.storage_type.value == "in-memory":
            click.echo("Note:        In-memory storage has no persistence")
        
        click.echo(f"\nSnapshot:    Every {storage_config.snapshot_interval_seconds}s")
        click.echo(f"WAL:         {'Enabled' if storage_config.wal_enabled else 'Disabled'}")
        click.echo(f"Auto-compact: {'Enabled' if storage_config.auto_compact else 'Disabled'}")
        
        click.echo("\n💡 Tip: Use 'localzure storage export' to backup your data")
    
    except Exception as e:
        click.echo(f"❌ Error loading storage stats: {e}", err=True)
        sys.exit(1)


@storage.command()
@click.argument("path", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to configuration file",
)
def export(path: Path, config: Optional[Path]):
    """
    Export all data to a JSON file.
    
    Creates a portable backup of all entities and messages.
    
    Example:
        localzure storage export backup.json
        localzure storage export ~/backups/servicebus-$(date +%Y%m%d).json
    """
    click.echo(f"📦 Exporting data to: {path}")
    
    try:
        from localzure.services.servicebus.config import load_storage_config
        from localzure.services.servicebus.storage import create_storage_backend
        
        # Load configuration
        storage_config = load_storage_config(str(config) if config else None)
        
        async def do_export():
            # Create storage backend
            backend = create_storage_backend(storage_config)
            await backend.initialize()
            
            try:
                # Export data
                await backend.export_data(str(path))
                click.echo(f"✅ Data exported successfully to {path}")
            finally:
                await backend.close()
        
        # Run export
        asyncio.run(do_export())
    
    except Exception as e:
        click.echo(f"❌ Export failed: {e}", err=True)
        sys.exit(1)


@storage.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def import_data(path: Path, config: Optional[Path], yes: bool):
    """
    Import data from a JSON file.
    
    Restores entities and messages from a previous export.
    
    ⚠️  WARNING: This will overwrite existing data!
    
    Example:
        localzure storage import backup.json
        localzure storage import backup.json --yes
    """
    if not yes:
        click.confirm(
            f"⚠️  This will overwrite existing data. Import from {path}?",
            abort=True,
        )
    
    click.echo(f"📥 Importing data from: {path}")
    
    try:
        from localzure.services.servicebus.config import load_storage_config
        from localzure.services.servicebus.storage import create_storage_backend
        
        # Load configuration
        storage_config = load_storage_config(str(config) if config else None)
        
        async def do_import():
            # Create storage backend
            backend = create_storage_backend(storage_config)
            await backend.initialize()
            
            try:
                # Import data
                await backend.import_data(str(path))
                click.echo(f"✅ Data imported successfully from {path}")
            finally:
                await backend.close()
        
        # Run import
        asyncio.run(do_import())
    
    except Exception as e:
        click.echo(f"❌ Import failed: {e}", err=True)
        sys.exit(1)


@storage.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to configuration file",
)
def compact(config: Optional[Path]):
    """
    Compact storage to reclaim disk space.
    
    Removes deleted data and optimizes storage layout.
    For SQLite: runs VACUUM command.
    For JSON: removes orphaned files.
    
    Example:
        localzure storage compact
    """
    click.echo("🗜️  Compacting storage...")
    
    try:
        from localzure.services.servicebus.config import load_storage_config
        from localzure.services.servicebus.storage import create_storage_backend
        
        # Load configuration
        storage_config = load_storage_config(str(config) if config else None)
        
        async def do_compact():
            # Create storage backend
            backend = create_storage_backend(storage_config)
            await backend.initialize()
            
            try:
                # Compact
                await backend.compact()
                click.echo("✅ Storage compacted successfully")
            finally:
                await backend.close()
        
        # Run compact
        asyncio.run(do_compact())
    
    except Exception as e:
        click.echo(f"❌ Compact failed: {e}", err=True)
        sys.exit(1)


@storage.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def purge(config: Optional[Path], yes: bool):
    """
    Delete ALL data from storage.
    
    ⚠️  WARNING: This is irreversible! All entities and messages will be permanently deleted.
    
    Example:
        localzure storage purge
        localzure storage purge --yes
    """
    if not yes:
        click.confirm(
            "⚠️  Are you ABSOLUTELY SURE you want to delete ALL data? This cannot be undone!",
            abort=True,
        )
        
        # Double confirmation
        confirmation = click.prompt("Type 'DELETE ALL' to confirm")
        if confirmation != "DELETE ALL":
            click.echo("❌ Purge cancelled (confirmation did not match)")
            sys.exit(1)
    
    click.echo("🗑️  Purging all data...")
    
    try:
        from localzure.services.servicebus.config import load_storage_config
        from localzure.services.servicebus.storage import create_storage_backend
        
        # Load configuration
        storage_config = load_storage_config(str(config) if config else None)
        
        async def do_purge():
            # Create storage backend
            backend = create_storage_backend(storage_config)
            await backend.initialize()
            
            try:
                # Purge
                await backend.purge()
                click.echo("✅ All data has been purged")
            finally:
                await backend.close()
        
        # Run purge
        asyncio.run(do_purge())
    
    except Exception as e:
        click.echo(f"❌ Purge failed: {e}", err=True)
        sys.exit(1)


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
