#!/usr/bin/env python3
"""
Script to run the XML Diploma Generator API.
Starts the FastAPI server with Uvicorn.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the python-xml-engine directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Run the FastAPI application."""
    parser = argparse.ArgumentParser(
        description="Run the XML Diploma Generator API"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8002,
        help="Port to bind the server to (default: 8002)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on file changes (development mode)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )

    args = parser.parse_args()

    try:
        import uvicorn
        from app.main import app

        print(f"Starting XML Diploma Generator API...")
        print(f"  Host: {args.host}")
        print(f"  Port: {args.port}")
        print(f"  Reload: {args.reload}")
        if not args.reload:
            print(f"  Workers: {args.workers}")

        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,
        )

    except ImportError as e:
        print(f"Error: Required packages not installed. {e}")
        print("Please install dependencies with: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
