from .registry import TestTypeRegistry
from .echo import EchocardiogramHandler
from .labs import LabResultsHandler

registry = TestTypeRegistry()
registry.register(EchocardiogramHandler())
registry.register(LabResultsHandler())

__all__ = ["registry", "TestTypeRegistry"]
