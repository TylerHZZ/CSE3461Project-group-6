"""F3 A is selected for a later stage; no delay or experiment is active."""
from ..protocol import AppError, EmptyEnhancementRequest, RequestContext


def handle_enhancement(ctx: RequestContext, request: EmptyEnhancementRequest) -> AppError:
    return AppError('FEATURE_NOT_IMPLEMENTED', 'Enhancement A is not implemented.', feature='f3')
