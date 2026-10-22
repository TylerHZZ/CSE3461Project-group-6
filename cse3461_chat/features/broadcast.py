"""F1 recipient selection over the shared read-only directory."""
from ..protocol import AppError, BroadcastRequest, FeatureOutcome, RequestContext, RoutePlan


def handle_broadcast(ctx: RequestContext, request: BroadcastRequest) -> FeatureOutcome:
    # Lookup-time snapshot by session ID: later joiners get no replay, the sender gets no echo.
    recipients = ctx.directory.others(ctx.sender.session_id)
    if not recipients:
        return AppError('NO_RECIPIENTS', 'No other users are connected.', feature='f1')
    return RoutePlan(recipients)
