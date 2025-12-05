#!/usr/bin/env python3
"""
LocalZure Bootstrap Script

This script helps you get started with LocalZure quickly.
It checks prerequisites, installs dependencies, and starts LocalZure.

Usage:
    python bootstrap.py              # Interactive setup
    python bootstrap.py --quick      # Quick start (skip prompts)
    python bootstrap.py --docker     # Use Docker
    python bootstrap.py --dev        # Development mode
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def print_banner():
    """Print LocalZure banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║     🌀 LocalZure - Local Azure Cloud Emulator           ║
    ║                                                          ║
    ║     Use Azure services locally, just like LocalStack    ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """
    print(banner)


def check_python_version():
    """Check if Python version is compatible"""
    print("📍 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True


def check_docker():
    """Check if Docker is available"""
    print("\n📍 Checking Docker...")
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"✅ Docker available: {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    print("⚠️  Docker not found (optional)")
    return False


def install_localzure(dev_mode=False):
    """Install LocalZure"""
    print("\n📦 Installing LocalZure...")
    
    if dev_mode:
        print("   Installing in development mode...")
        cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "."]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print("✅ LocalZure installed successfully")
            return True
        else:
            print(f"❌ Installation failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Installation timed out")
        return False


def verify_installation():
    """Verify LocalZure is installed correctly"""
    print("\n📍 Verifying installation...")
    try:
        result = subprocess.run(
            ["localzure", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    print("❌ LocalZure command not found")
    return False


def start_localzure(mode="normal", port=7071):
    """Start LocalZure"""
    print(f"\n🚀 Starting LocalZure on port {port}...")
    
    cmd = ["localzure", "start", "--port", str(port)]
    
    if mode == "dev":
        print("   Development mode with auto-reload enabled")
        cmd.extend(["--reload", "--log-level", "DEBUG"])
    
    try:
        print("\n" + "="*60)
        print(f"   LocalZure starting at http://127.0.0.1:{port}")
        print("="*60)
        print("\n📝 Press Ctrl+C to stop\n")
        
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\n👋 LocalZure stopped")


def start_docker():
    """Start LocalZure with Docker"""
    print("\n🐳 Starting LocalZure with Docker...")
    
    # Check if docker-compose exists
    compose_file = Path("docker-compose.yml")
    if compose_file.exists():
        print("   Using docker-compose...")
        try:
            subprocess.run(["docker-compose", "up", "-d"], check=True)
            print("\n✅ LocalZure started in Docker")
            print("   View logs: docker-compose logs -f")
            print("   Stop: docker-compose down")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start: {e}")
    else:
        print("   Using docker run...")
        try:
            subprocess.run([
                "docker", "run", "-d",
                "--name", "localzure",
                "-p", "7071:7071",
                "localzure/localzure:latest"
            ], check=True)
            print("\n✅ LocalZure started in Docker")
            print("   View logs: docker logs -f localzure")
            print("   Stop: docker stop localzure")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start: {e}")


def wait_for_health(port=7071, timeout=30):
    """Wait for LocalZure to be healthy"""
    print(f"\n⏳ Waiting for LocalZure to be ready...")
    
    import urllib.request
    url = f"http://127.0.0.1:{port}/health"
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = urllib.request.urlopen(url, timeout=2)
            if response.status == 200:
                print("✅ LocalZure is ready!")
                return True
        except:
            pass
        time.sleep(1)
    
    print("❌ LocalZure did not become ready in time")
    return False


def show_next_steps(port=7071):
    """Show next steps"""
    print("\n" + "="*60)
    print("🎉 LocalZure Setup Complete!")
    print("="*60)
    print("\n📚 Quick Start Guide:")
    print(f"\n1. Health Check:")
    print(f"   curl http://127.0.0.1:{port}/health")
    print(f"\n2. API Documentation:")
    print(f"   Open http://127.0.0.1:{port}/docs in your browser")
    print(f"\n3. Try the example:")
    print("   python examples/test_servicebus.py")
    print("\n4. Use in your code:")
    print("""
   from azure.servicebus import ServiceBusClient, ServiceBusMessage
   
   connection_string = "Endpoint=sb://127.0.0.1:7071/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=dummy"
   client = ServiceBusClient.from_connection_string(connection_string)
    """)
    print("\n📖 Documentation:")
    print("   - Quick Start: QUICKSTART.md")
    print("   - Integration: INTEGRATION.md")
    print("   - Docker: DOCKER.md")
    print("\n💡 CLI Commands:")
    print("   localzure start       # Start LocalZure")
    print("   localzure status      # Check status")
    print("   localzure config      # Show config")
    print("   localzure version     # Show version")
    print("\n" + "="*60)


def interactive_setup():
    """Interactive setup wizard"""
    print_banner()
    
    # Check prerequisites
    if not check_python_version():
        return False
    
    has_docker = check_docker()
    
    # Ask user preference
    print("\n" + "="*60)
    print("Setup Options:")
    print("="*60)
    print("\n1. Install and run locally (Recommended)")
    if has_docker:
        print("2. Run with Docker")
    print("3. Development mode (with auto-reload)")
    print("4. Exit")
    
    choice = input("\nChoose option [1]: ").strip() or "1"
    
    if choice == "4":
        print("👋 Goodbye!")
        return True
    
    if choice == "2" and has_docker:
        start_docker()
        time.sleep(3)
        wait_for_health()
        show_next_steps()
        return True
    
    # Install LocalZure
    dev_mode = (choice == "3")
    if not install_localzure(dev_mode=dev_mode):
        return False
    
    # Verify installation
    if not verify_installation():
        return False
    
    # Ask about port
    port = input("\nPort to use [7071]: ").strip() or "7071"
    try:
        port = int(port)
    except ValueError:
        port = 7071
    
    # Show next steps first
    show_next_steps(port)
    
    # Ask to start
    start_now = input("\nStart LocalZure now? [Y/n]: ").strip().lower()
    if start_now in ["", "y", "yes"]:
        mode = "dev" if dev_mode else "normal"
        start_localzure(mode=mode, port=port)
    
    return True


def quick_setup():
    """Quick setup without prompts"""
    print_banner()
    check_python_version()
    install_localzure()
    verify_installation()
    show_next_steps()
    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="LocalZure Bootstrap - Get started with LocalZure quickly"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick install without prompts"
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Use Docker"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7071,
        help="Port to use (default: 7071)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.docker:
            print_banner()
            check_docker()
            start_docker()
            time.sleep(3)
            wait_for_health(args.port)
            show_next_steps(args.port)
        elif args.quick:
            quick_setup()
        else:
            interactive_setup()
    except KeyboardInterrupt:
        print("\n\n👋 Setup interrupted")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
