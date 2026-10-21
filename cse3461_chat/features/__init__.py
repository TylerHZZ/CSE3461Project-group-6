"""Explicit immutable skeleton wiring; no dynamic plugin mechanism."""
from dataclasses import dataclass
from typing import Callable

from ..protocol import FeatureDescriptor
from .broadcast import handle_broadcast
from .private_chat import handle_private
from .enhancement import handle_enhancement


@dataclass(frozen=True)
class HandlerTable:
    broadcast: Callable = handle_broadcast
    private: Callable = handle_private
    enhancement: Callable = handle_enhancement
    descriptors: tuple[FeatureDescriptor, ...] = tuple(FeatureDescriptor(f) for f in ('f1','f2','f3'))


def build_handlers() -> HandlerTable:
    return HandlerTable()
