"""Explicit immutable feature wiring; no dynamic plugin mechanism."""
from dataclasses import dataclass
from typing import Callable

from ..config import FEATURE_CHOICES
from ..protocol import FeatureDescriptor
from .broadcast import handle_broadcast
from .private_chat import handle_private
from .enhancement import handle_enhancement


@dataclass(frozen=True)
class HandlerTable:
    broadcast: Callable = handle_broadcast
    private: Callable = handle_private
    enhancement: Callable = handle_enhancement
    descriptors: tuple[FeatureDescriptor, ...] = (FeatureDescriptor('f1', True, False), FeatureDescriptor('f2', True, False), FeatureDescriptor('f3', True, False, 'A'))


def build_handlers(features='none') -> HandlerTable:
    if features not in FEATURE_CHOICES:
        raise ValueError('Use one of: '+', '.join(FEATURE_CHOICES)+'.')
    enabled = features.split(',')
    return HandlerTable(descriptors=(FeatureDescriptor('f1', True, 'f1' in enabled),
        FeatureDescriptor('f2', True, 'f2' in enabled), FeatureDescriptor('f3', True, 'f3' in enabled, 'A')))
