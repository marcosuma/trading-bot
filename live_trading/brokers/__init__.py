"""
Broker Adapters for IBKR and OANDA.
"""
from .base_broker import BaseBroker

# Try to import IBKR broker, but make it optional
try:
    from .ibkr_broker import IBKRBroker
    __all__ = ["BaseBroker", "IBKRBroker"]
except ImportError:
    IBKRBroker = None
    __all__ = ["BaseBroker"]

