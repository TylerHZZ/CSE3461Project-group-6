"""F2 recipient selection over the shared read-only directory."""
from ..protocol import AppError, PrivateRequest, FeatureOutcome, RequestContext, RoutePlan


def handle_private(ctx: RequestContext, request: PrivateRequest) -> FeatureOutcome:
    if request.to == ctx.sender.username:
        return AppError('SELF_TARGET', 'Choose another user for a private message.', feature='f2')
    target = ctx.directory.find(request.to)
    if target is None:
        return AppError('USER_NOT_FOUND', 'The target user is not connected.', feature='f2')
    # Keep the captured session ID: a later same-name login is a different recipient.
    return RoutePlan((target,))
