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
    descriptors: tuple[FeatureDescriptor, ...] = (FeatureDescriptor('f1'), FeatureDescriptor('f2', True, False), FeatureDescriptor('f3', True, False, 'A'))


def build_handlers(features='none') -> HandlerTable:
    if features not in ('none', 'f2', 'f3', 'f2,f3'):
        raise ValueError('Only none, f2, f3 or f2,f3 can be enabled.')
    return HandlerTable(descriptors=(FeatureDescriptor('f1'),
        FeatureDescriptor('f2', True, 'f2' in features.split(',')), FeatureDescriptor('f3', True, 'f3' in features.split(','), 'A')))
