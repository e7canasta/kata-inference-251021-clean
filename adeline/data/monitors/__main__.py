"""
Entry point for monitors - defaults to data_monitor
Usage:
    python -m adeline.data.monitors          # Run data monitor
    python -m adeline.data.monitors data     # Run data monitor
    python -m adeline.data.monitors status   # Run status monitor
"""
import sys

if __name__ == "__main__":
    monitor_type = sys.argv[1] if len(sys.argv) > 1 else "data"

    if monitor_type == "status":
        from .status_monitor import main
    else:
        from .data_monitor import main

    # Remove monitor type from argv so the monitor's argparse works correctly
    if len(sys.argv) > 1 and sys.argv[1] in ["data", "status"]:
        sys.argv.pop(1)

    main()
