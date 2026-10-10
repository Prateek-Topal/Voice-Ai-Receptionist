"""Entry point.

Usage:
    python main.py console   # talk to the agent through your mic/speakers (local test)
    python main.py dev       # connect to LiveKit Cloud (browser Agent Console / phone calls)
    python main.py start     # production mode
"""

from livekit.agents import cli

from receptionist.agent import server

if __name__ == "__main__":
    cli.run_app(server)
