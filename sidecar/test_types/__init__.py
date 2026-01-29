from .registry import TestTypeRegistry
from .echo import EchocardiogramHandler

registry = TestTypeRegistry()
registry.register(EchocardiogramHandler())

__all__ = ["registry", "TestTypeRegistry"]
