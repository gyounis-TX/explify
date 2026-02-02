from .registry import TestTypeRegistry
from .echo import EchocardiogramHandler
from .labs import LabResultsHandler
from .stress import StressTestHandler
from .carotid import CarotidDopplerHandler
from .arterial import ArterialDopplerHandler
from .venous import VenousDopplerHandler

registry = TestTypeRegistry()
registry.register(EchocardiogramHandler())
registry.register(LabResultsHandler())
registry.register(StressTestHandler())
registry.register(CarotidDopplerHandler())
registry.register(ArterialDopplerHandler())
registry.register(VenousDopplerHandler())

__all__ = ["registry", "TestTypeRegistry"]
