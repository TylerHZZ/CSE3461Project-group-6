"""F1 integration seam; recipient selection is intentionally unavailable."""
from ..protocol import AppError, BroadcastRequest, FeatureOutcome, RequestContext


def handle_broadcast(ctx: RequestContext, request: BroadcastRequest) -> FeatureOutcome:
    return AppError('FEATURE_NOT_IMPLEMENTED', 'Broadcast is not implemented.', feature='f1')
