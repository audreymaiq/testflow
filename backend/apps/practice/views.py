"""Thin API boundary for practice and timed sessions."""

import secrets

from drf_spectacular.utils import extend_schema
from pydantic import ValidationError as ConfigValidationError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .schemas import SessionConfig
from .serializers import (
    AnswerResponseSerializer,
    CreateSessionSerializer,
    EmptySerializer,
    ResultResponseSerializer,
    SaveAnswerSerializer,
    SessionResponseSerializer,
)
from .services import (
    create_session,
    result_payload,
    save_answer,
    session_payload,
    skip_question,
    submit_session,
)


class SessionListCreateView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CreateSessionSerializer

    @extend_schema(responses={201: SessionResponseSerializer})
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        exam_id = values.pop("exam_id")
        mode = values.pop("mode")
        try:
            config = SessionConfig.model_validate({**values, "seed": secrets.randbits(63)})
        except ConfigValidationError as exc:
            raise ValidationError(exc.errors(include_url=False)) from exc
        session = create_session(user=request.user, exam_id=exam_id, mode=mode, config=config)
        return Response(session_payload(session.id, request.user), status=status.HTTP_201_CREATED)


class SessionDetailView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = SessionResponseSerializer

    def get(self, request, session_id):
        return Response(session_payload(session_id, request.user))


class AnswerView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = SaveAnswerSerializer

    @extend_schema(responses={200: AnswerResponseSerializer})
    def put(self, request, session_id, question_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            save_answer(session_id, question_id, user=request.user, **serializer.validated_data)
        )


class SkipView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = EmptySerializer

    @extend_schema(responses={200: AnswerResponseSerializer})
    def post(self, request, session_id, question_id):
        return Response(skip_question(session_id, question_id, user=request.user))


class SubmitView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = EmptySerializer

    @extend_schema(responses={200: ResultResponseSerializer})
    def post(self, request, session_id):
        return Response(submit_session(session_id, user=request.user))


class ResultView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ResultResponseSerializer

    def get(self, request, session_id):
        return Response(result_payload(session_id, request.user))
