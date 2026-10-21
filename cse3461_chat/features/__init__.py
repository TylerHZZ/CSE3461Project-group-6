"""Explicit immutable feature wiring; no dynamic plugin mechanism."""
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
    descriptors: tuple[FeatureDescriptor, ...] = (FeatureDescriptor('f1'), FeatureDescriptor('f2', True, False), FeatureDescriptor('f3'))


def build_handlers(features='none') -> HandlerTable:
    if features not in ('none', 'f2'):
        raise ValueError('Only none or f2 can be enabled.')
    return HandlerTable(descriptors=(FeatureDescriptor('f1'),
        FeatureDescriptor('f2', True, features == 'f2'), FeatureDescriptor('f3')))
