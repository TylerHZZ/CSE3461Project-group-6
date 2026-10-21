"""Request validation, feature dispatch and shared queued chat publication."""
import time
from dataclasses import asdict
from uuid import uuid4
from .protocol import (AppError, BroadcastRequest, PrivateRequest, EmptyEnhancementRequest,
                       RequestContext, RoutePlan, PublishResult, DeliveryMeta, Envelope, FEATURE_TYPES,
                       valid_id, valid_username, validate_message, capabilities, make_message, error_message)


class Publisher:
    def __init__(self, manager):
        self.manager = manager

    def publish(self, ctx: RequestContext, request: BroadcastRequest | PrivateRequest,
                plan: RoutePlan) -> PublishResult | AppError:
        private = isinstance(request, PrivateRequest)
        feature = 'f2' if private else 'f1'
        if (any(target.session_id == ctx.sender.session_id for target in plan.recipients) or
                (private and (len(plan.recipients) != 1 or plan.recipients[0].username != request.to))):
            return AppError('INTERNAL_ERROR', 'Invalid recipient plan.', True, feature)
        message_id = str(uuid4())
        selected = len(plan.recipients)
        self.manager._emit('route_selected', dict(message_id=message_id, feature=feature,
            origin_session_id=ctx.sender.session_id, origin_request_id=ctx.request_id,
            selected_count=selected, target_session_ids=tuple(t.session_id for t in plan.recipients)))
        message = make_message('chat_message', None, dict(message_id=message_id,
            mode='private' if private else 'broadcast', sender=ctx.sender.username,
            recipient=request.to if private else None, text=request.text))
        queued = 0
        for target in plan.recipients:
            meta = DeliveryMeta(message_id, ctx.sender.session_id, ctx.request_id,
                                feature, target.session_id, time.monotonic_ns())
            admission = self.manager.enqueue(target.session_id, message, meta)
            if admission.queued:
                queued += 1
            elif admission.reason == 'full':
                # Close outside the queue/registry critical section, then continue.
                self.manager.close(target.session_id, 'recipient_queue_full', None, False)
        status = 'queued' if queued == selected else ('partial' if queued else 'not_queued')
        return PublishResult(message_id, status, selected, queued, selected-queued)


class Dispatcher:
    def __init__(self, manager, handlers, events):
        self.manager, self.handlers, self.events = manager, handlers, events
        self.publisher = Publisher(manager)
        self.capabilities = capabilities(handlers.descriptors)
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
            reply = make_message('registered', rid, dict(session_id=session_id, username=message.data['username'], features=self.capabilities))
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
        if isinstance(outcome, PublishResult):
            reply = make_message('send_result', rid, asdict(outcome))
            admission = self.manager.enqueue(session_id, reply, None)
            if not admission.queued:
                self.manager.close(session_id, 'control_queue_'+admission.reason, None, False)
            return
        if not isinstance(outcome, AppError):
            outcome = AppError('INTERNAL_ERROR', 'Invalid feature outcome.', True, feature)
        self.reject(session_id, outcome, rid, kind)
