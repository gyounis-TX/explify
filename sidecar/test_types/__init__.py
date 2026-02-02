from .registry import TestTypeRegistry
from .echo import EchocardiogramHandler
from .labs import LabResultsHandler
from .stress import StressTestHandler

registry = TestTypeRegistry()
registry.register(EchocardiogramHandler())
registry.register(LabResultsHandler())
registry.register(StressTestHandler())

__all__ = ["registry", "TestTypeRegistry"]
