"""Friday - AI Coding Assistant CLI

Main entry point for the Friday conversational coding CLI.
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from friday.cli import FridayCLI


def main():
    """Main entry point for Friday CLI"""
    import argparse
    parser = argparse.ArgumentParser(prog="friday", description="Friday - AI Coding Assistant CLI")
    parser.add_argument("-n", "--no-banner", action="store_true", help="Disable startup banner")
    parser.add_argument("-m", "--minimal", action="store_true", help="Use minimal banner (no ASCII art or tips)")
    parser.add_argument("-a", "--ascii", choices=["compact", "block"], help="Choose ASCII art variant for banner")
    parser.add_argument("-t", "--theme", choices=["dark", "light", "hc"], help="Theme profile for colors and prompt styling")
    args = parser.parse_args()

    # Map flags to env vars consumed by FridayCLI
    if args.no_banner:
        os.environ["FRIDAY_NO_BANNER"] = "1"
    if args.minimal:
        os.environ["FRIDAY_MINIMAL"] = "1"
    if args.ascii:
        os.environ["FRIDAY_ASCII_VARIANT"] = args.ascii
    if args.theme:
        os.environ["FRIDAY_THEME_PROFILE"] = args.theme

    cli = FridayCLI()
    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
