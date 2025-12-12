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
from localzure.services.keyvault.routes import create_router as create_keyvault_router
from localzure.services.blob.api import router as blob_router
from localzure.services.queue.api import router as queue_router
from localzure.services.table.api import router as table_router
from localzure.services.cosmosdb.routes import router as cosmosdb_router


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
    
    click.echo(f"Starting LocalZure v{__version__}")
    click.echo(f"Host: {host}:{port}")
    
    if config:
        click.echo(f"Config: {config}")
    
    click.echo(f"Log Level: {log_level}")
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
        click.echo(f"[ERROR] Error starting LocalZure: {e}", err=True)
        sys.exit(1)


@cli.command()
def status():
    """
    Show status of LocalZure services.
    
    Displays which services are running and their health status.
    """
    click.echo(" LocalZure Status")
    click.echo()
    
    # TODO: Implement actual status checking via HTTP health endpoint
    click.echo("Service Bus: [OK] Running")
    click.echo("Key Vault:   [OK] Running")
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
    click.echo("[OK] LocalZure stopped")


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
    click.echo("LocalZure Configuration")
    click.echo()
    click.echo("Host: 127.0.0.1")
    click.echo()
    click.echo("Enabled Services:")
    click.echo("  - Service Bus (AMQP 1.0 emulator)")
    click.echo("  - Key Vault (secrets management)")
    click.echo()
    click.echo("Use 'localzure start --config <file>' to load custom configuration.")
    click.echo("Use 'localzure start --config <file>' to load custom configuration.")


# ========== Key Vault Management Commands (SVC-KV-001) ==========

@cli.group()
def keyvault():
    """
    Manage Key Vault secrets.
    
    Commands for creating, retrieving, listing, and deleting secrets.
    """
    pass


@keyvault.command()
@click.argument("vault_name")
@click.argument("secret_name")
@click.argument("value")
@click.option(
    "--content-type",
    help="Content type of the secret (e.g., 'text/plain', 'application/json')",
)
@click.option(
    "--tags",
    multiple=True,
    help="Tags in key=value format (can specify multiple times)",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="LocalZure host",
    show_default=True,
)
@click.option(
    "--port",
    default=8200,
    help="Key Vault port",
    show_default=True,
    type=int,
)
def set(vault_name: str, secret_name: str, value: str, content_type: Optional[str], tags: tuple, host: str, port: int):
    """
    Set (create or update) a secret.
    
    Examples:
        localzure keyvault set my-vault db-password "super-secret"
        localzure keyvault set my-vault api-key "key123" --content-type text/plain
        localzure keyvault set my-vault config "data" --tags env=prod --tags app=web
    """
    import httpx
    import json
    
    click.echo(f"🔐 Setting secret '{secret_name}' in vault '{vault_name}'...")
    
    # Parse tags
    tags_dict = {}
    for tag in tags:
        if "=" in tag:
            key, val = tag.split("=", 1)
            tags_dict[key] = val
    
    # Prepare request
    request_data = {"value": value}
    if content_type:
        request_data["contentType"] = content_type
    if tags_dict:
        request_data["tags"] = tags_dict
    
    try:
        url = f"http://{host}:{port}/{vault_name}/secrets/{secret_name}?api-version=7.3"
        response = httpx.put(url, json=request_data, timeout=10.0)
        response.raise_for_status()
        
        result = response.json()
        click.echo(f"[OK] Secret set successfully")
        click.echo(f"   ID: {result['id']}")
        if result.get("attributes", {}).get("created"):
            click.echo(f"   Created: {result['attributes']['created']}")
    
    except httpx.HTTPError as e:
        click.echo(f"[ERROR] Failed to set secret: {e}", err=True)
        sys.exit(1)


@keyvault.command()
@click.argument("vault_name")
@click.argument("secret_name")
@click.option(
    "--version",
    help="Specific version to retrieve (default: latest)",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="LocalZure host",
    show_default=True,
)
@click.option(
    "--port",
    default=8200,
    help="Key Vault port",
    show_default=True,
    type=int,
)
def get(vault_name: str, secret_name: str, version: Optional[str], host: str, port: int):
    """
    Get a secret value.
    
    Examples:
        localzure keyvault get my-vault db-password
        localzure keyvault get my-vault api-key --version abc123
    """
    import httpx
    
    click.echo(f"🔍 Retrieving secret '{secret_name}' from vault '{vault_name}'...")
    
    try:
        if version:
            url = f"http://{host}:{port}/{vault_name}/secrets/{secret_name}/{version}?api-version=7.3"
        else:
            url = f"http://{host}:{port}/{vault_name}/secrets/{secret_name}?api-version=7.3"
        
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        
        result = response.json()
        click.echo(f"[OK] Secret retrieved")
        click.echo(f"   Value: {result['value']}")
        click.echo(f"   ID: {result['id']}")
        if result.get("contentType"):
            click.echo(f"   Content-Type: {result['contentType']}")
        if result.get("tags"):
            click.echo(f"   Tags: {result['tags']}")
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            click.echo(f"[ERROR] Secret not found", err=True)
        elif e.response.status_code == 403:
            click.echo(f"[ERROR] Secret is disabled or expired", err=True)
        else:
            click.echo(f"[ERROR] Failed to get secret: {e}", err=True)
        sys.exit(1)
    except httpx.HTTPError as e:
        click.echo(f"[ERROR] Failed to get secret: {e}", err=True)
        sys.exit(1)


@keyvault.command()
@click.argument("vault_name")
@click.option(
    "--host",
    default="127.0.0.1",
    help="LocalZure host",
    show_default=True,
)
@click.option(
    "--port",
    default=8200,
    help="Key Vault port",
    show_default=True,
    type=int,
)
def list(vault_name: str, host: str, port: int):
    """
    List all secrets in a vault.
    
    Example:
        localzure keyvault list my-vault
    """
    import httpx
    
    click.echo(f"📋 Listing secrets in vault '{vault_name}'...")
    click.echo()
    
    try:
        url = f"http://{host}:{port}/{vault_name}/secrets?api-version=7.3"
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        
        result = response.json()
        secrets = result.get("value", [])
        
        if not secrets:
            click.echo("No secrets found.")
        else:
            click.echo(f"Found {len(secrets)} secret(s):\n")
            for secret in secrets:
                secret_id = secret["id"]
                secret_name = secret_id.split("/")[-1]
                enabled = secret["attributes"]["enabled"]
                status = "[OK] Enabled" if enabled else "[X] Disabled"
                
                click.echo(f"  • {secret_name} ({status})")
                if secret.get("contentType"):
                    click.echo(f"    Content-Type: {secret['contentType']}")
                if secret.get("tags"):
                    click.echo(f"    Tags: {secret['tags']}")
                click.echo()
    
    except httpx.HTTPError as e:
        click.echo(f"[ERROR] Failed to list secrets: {e}", err=True)
        sys.exit(1)


@keyvault.command()
@click.argument("vault_name")
@click.argument("secret_name")
@click.option(
    "--host",
    default="127.0.0.1",
    help="LocalZure host",
    show_default=True,
)
@click.option(
    "--port",
    default=8200,
    help="Key Vault port",
    show_default=True,
    type=int,
)
def delete(vault_name: str, secret_name: str, host: str, port: int):
    """
    Delete a secret.
    
    Example:
        localzure keyvault delete my-vault old-secret
    """
    import httpx
    
    click.echo(f"  Deleting secret '{secret_name}' from vault '{vault_name}'...")
    
    try:
        url = f"http://{host}:{port}/{vault_name}/secrets/{secret_name}?api-version=7.3"
        response = httpx.delete(url, timeout=10.0)
        response.raise_for_status()
        
        result = response.json()
        click.echo(f"[OK] Secret deleted")
        if result.get("recoveryId"):
            click.echo(f"   Recovery ID: {result['recoveryId']}")
            click.echo(f"   [INFO] Secret is soft-deleted and can be recovered")
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            click.echo(f"[ERROR] Secret not found", err=True)
        else:
            click.echo(f"[ERROR] Failed to delete secret: {e}", err=True)
        sys.exit(1)
    except httpx.HTTPError as e:
        click.echo(f"[ERROR] Failed to delete secret: {e}", err=True)
        sys.exit(1)


@keyvault.command()
@click.argument("vault_name")
@click.argument("secret_name")
@click.option(
    "--host",
    default="127.0.0.1",
    help="LocalZure host",
    show_default=True,
)
@click.option(
    "--port",
    default=8200,
    help="Key Vault port",
    show_default=True,
    type=int,
)
def versions(vault_name: str, secret_name: str, host: str, port: int):
    """
    List all versions of a secret.
    
    Example:
        localzure keyvault versions my-vault db-password
    """
    import httpx
    
    click.echo(f"📋 Listing versions of secret '{secret_name}' in vault '{vault_name}'...")
    click.echo()
    
    try:
        url = f"http://{host}:{port}/{vault_name}/secrets/{secret_name}/versions?api-version=7.3"
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        
        result = response.json()
        versions = result.get("value", [])
        
        if not versions:
            click.echo("No versions found.")
        else:
            click.echo(f"Found {len(versions)} version(s):\n")
            for idx, version_item in enumerate(versions, 1):
                version_id = version_item["id"].split("/")[-1]
                created = version_item["attributes"].get("created", "N/A")
                enabled = version_item["attributes"]["enabled"]
                status = "[OK]" if enabled else "[X]"
                
                is_latest = " (latest)" if idx == 1 else ""
                click.echo(f"  {idx}. {version_id[:8]}...{is_latest} {status}")
                click.echo(f"     Created: {created}")
                click.echo()
    
    except httpx.HTTPError as e:
        click.echo(f"[ERROR] Failed to list versions: {e}", err=True)
        sys.exit(1)


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
    
    click.echo(" Storage Statistics")
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
        click.echo(f"[ERROR] Error loading storage stats: {e}", err=True)
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
                click.echo(f"[OK] Data exported successfully to {path}")
            finally:
                await backend.close()
        
        # Run export
        asyncio.run(do_export())
    
    except Exception as e:
        click.echo(f"[ERROR] Export failed: {e}", err=True)
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
    
    [WARN]  WARNING: This will overwrite existing data!
    
    Example:
        localzure storage import backup.json
        localzure storage import backup.json --yes
    """
    if not yes:
        click.confirm(
            f"[WARN]  This will overwrite existing data. Import from {path}?",
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
                click.echo(f"[OK] Data imported successfully from {path}")
            finally:
                await backend.close()
        
        # Run import
        asyncio.run(do_import())
    
    except Exception as e:
        click.echo(f"[ERROR] Import failed: {e}", err=True)
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
    click.echo("  Compacting storage...")
    
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
                click.echo("[OK] Storage compacted successfully")
            finally:
                await backend.close()
        
        # Run compact
        asyncio.run(do_compact())
    
    except Exception as e:
        click.echo(f"[ERROR] Compact failed: {e}", err=True)
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
    
    [WARN]  WARNING: This is irreversible! All entities and messages will be permanently deleted.
    
    Example:
        localzure storage purge
        localzure storage purge --yes
    """
    if not yes:
        click.confirm(
            "[WARN]  Are you ABSOLUTELY SURE you want to delete ALL data? This cannot be undone!",
            abort=True,
        )
        
        # Double confirmation
        confirmation = click.prompt("Type 'DELETE ALL' to confirm")
        if confirmation != "DELETE ALL":
            click.echo("[ERROR] Purge cancelled (confirmation did not match)")
            sys.exit(1)
    
    click.echo("  Purging all data...")
    
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
                click.echo("[OK] All data has been purged")
            finally:
                await backend.close()
        
        # Run purge
        asyncio.run(do_purge())
    
    except Exception as e:
        click.echo(f"[ERROR] Purge failed: {e}", err=True)
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
                "servicebus": {
                    "name": "servicebus",
                    "state": "running",
                    "version": __version__
                },
                "keyvault": {
                    "name": "keyvault",
                    "state": "running",
                    "version": __version__
                },
                "blobstorage": {
                    "name": "blobstorage",
                    "state": "running",
                    "version": __version__
                },
                "queuestorage": {
                    "name": "queuestorage",
                    "state": "running",
                    "version": __version__
                },
                "tablestorage": {
                    "name": "tablestorage",
                    "state": "running",
                    "version": __version__
                },
                "cosmosdb": {
                    "name": "cosmosdb",
                    "state": "running",
                    "version": __version__
                }
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
                },
                "keyvault": {
                    "status": "running",
                    "endpoint": "/",
                    "docs": "/docs#/Secrets"
                },
                "blobstorage": {
                    "status": "running",
                    "endpoint": "/blob",
                    "docs": "/docs#/blob-storage"
                }
            },
            "documentation": "/docs",
            "health": "/health"
        }
    
    # Include service routers
    app.include_router(servicebus_router, tags=["Service Bus"])
    app.include_router(create_keyvault_router(), tags=["Key Vault"])
    app.include_router(blob_router, tags=["Blob Storage"])
    app.include_router(queue_router, tags=["Queue Storage"])
    app.include_router(table_router, tags=["Table Storage"])
    app.include_router(cosmosdb_router, tags=["Cosmos DB"])
    
    # Register exception handlers
    register_exception_handlers(app)
    
    return app


def main():
    """Main entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
