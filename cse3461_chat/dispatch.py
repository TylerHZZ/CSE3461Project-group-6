"""Request validation and control replies. Chat publication remains a stub."""
from .protocol import (AppError, BroadcastRequest, PrivateRequest, EmptyEnhancementRequest,
                       RequestContext, RoutePlan, PublishResult, Envelope, FEATURE_TYPES,
                       valid_id, valid_username, validate_message, capabilities, make_message, error_message)


class Publisher:
    def publish(self, ctx: RequestContext, request: BroadcastRequest | PrivateRequest,
                plan: RoutePlan) -> PublishResult | AppError:
        feature = 'f1' if isinstance(request, BroadcastRequest) else 'f2'
        return AppError('FEATURE_NOT_IMPLEMENTED', 'Chat publication is not implemented.', feature=feature)


class Dispatcher:
    def __init__(self, manager, handlers, events):
        self.manager, self.handlers, self.events = manager, handlers, events
        self.publisher = Publisher()
        self._descriptors = {d.id: d for d in handlers.descriptors}

    def reject(self, session_id, error, request_id=None, kind=None, drain=True):
        self.manager._emit('request_rejected', dict(session_id=session_id, request_id=request_id,
                                                   type=kind, error_code=error.code, feature=error.feature))
        reply = error_message(error, request_id)
        if error.fatal:
            self.manager.close(session_id, error.code, reply if drain else None, drain)
        else:
            result = self.manager.enqueue(session_id, reply, None)
            if not result.queued:
                self.manager.close(session_id, 'control_queue_'+result.reason, None, False)

    def handle(self, session_id: str, envelope: Envelope, received_ns: int) -> None:
        if self.manager.state(session_id) in ('closing', 'closed'):
            return
        rid, kind = envelope.request_id, envelope.type
        if envelope.v != 1:
            self.reject(session_id, AppError('UNSUPPORTED_VERSION', 'Only protocol v1 is supported.', True),
                        rid if valid_id(rid) else None, kind)
            return
        if not valid_id(rid) or not self.manager.consume_id(session_id, rid):
            self.reject(session_id, AppError('BAD_REQUEST_ID', 'Request IDs must strictly increase.', True), None, kind)
            return
        message = validate_message(envelope, 'c2s')
        if isinstance(message, AppError):
            if kind == 'register':
                requested_username = envelope.data.get('username')
                self.manager._emit('registration_result', dict(session_id=session_id,
                    requested_username=requested_username if valid_username(requested_username) else None,
                    accepted=False, error_code=message.code))
            self.reject(session_id, message, rid, kind)
            return
        if kind == 'disconnect':
            self.manager.close(session_id, 'client_request', make_message('bye', rid, {'reason':'client_request'}), True)
            return
        if kind == 'register':
            reply = make_message('registered', rid, dict(session_id=session_id, username=message.data['username'], features=capabilities()))
            result = self.manager.register(session_id, message.data['username'], reply)
            if isinstance(result, AppError):
                self.reject(session_id, result, None if result.code == 'REGISTRATION_TIMEOUT' else rid, kind)
            return
        sender = self.manager.view(session_id)
        if sender is None:
            self.reject(session_id, AppError('NOT_REGISTERED', 'Register before submitting feature requests.'), rid, kind)
            return
        feature = FEATURE_TYPES[kind]
        descriptor = self._descriptors[feature]
        if not descriptor.implemented:
            self.reject(session_id, AppError('FEATURE_NOT_IMPLEMENTED', 'This feature is not implemented.', feature=feature), rid, kind)
            return
        if not descriptor.enabled:
            self.reject(session_id, AppError('FEATURE_DISABLED', 'This feature is disabled.', feature=feature), rid, kind)
            return
        ctx = RequestContext(sender, rid, received_ns, self.manager.directory)
        if kind == 'broadcast_send':
            request = BroadcastRequest(message.data['text'])
            outcome = self.handlers.broadcast(ctx, request)
        elif kind == 'private_send':
            request = PrivateRequest(message.data['to'], message.data['text'])
            outcome = self.handlers.private(ctx, request)
        else:
            request = EmptyEnhancementRequest()
            outcome = self.handlers.enhancement(ctx, request)
        if isinstance(outcome, RoutePlan) and isinstance(request, (BroadcastRequest, PrivateRequest)):
            outcome = self.publisher.publish(ctx, request, outcome)
        if not isinstance(outcome, AppError):
            outcome = AppError('INTERNAL_ERROR', 'Invalid feature outcome.', True, feature)
        self.reject(session_id, outcome, rid, kind)
