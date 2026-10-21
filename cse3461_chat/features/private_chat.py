"""F2 integration seam; recipient selection is intentionally unavailable."""
from ..protocol import AppError, PrivateRequest, FeatureOutcome, RequestContext


def handle_private(ctx: RequestContext, request: PrivateRequest) -> FeatureOutcome:
    return AppError('FEATURE_NOT_IMPLEMENTED', 'Private messaging is not implemented.', feature='f2')
