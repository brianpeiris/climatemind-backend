import random
import typing
import uuid

import pytest
from flask import url_for
from flask.testing import FlaskClient
from mock import mock

from app.conversations.enums import (
    ConversationUserARating,
    ConversationState,
)
from app.factories import ConversationsFactory, faker
from app.models import Conversations, Users

RANDOM_CONVERSATION_STATE = random.choice(list([s.value for s in ConversationState]))


def is_uuid(string):
    try:
        uuid.UUID(string)
        ok = True
    except ValueError:
        ok = False
    return ok


@pytest.mark.skip("FIXME")
@pytest.mark.integration
@pytest.mark.parametrize(
    "request_data,status_code",
    [
        (
            {
                "receiverName": faker.name(),
                "state": RANDOM_CONVERSATION_STATE,
            },
            200,
        ),
        (  # unable to use together
            {
                "userARating": ConversationUserARating.EXCELLENT,
                "state": RANDOM_CONVERSATION_STATE,
            },
            422,
        ),
    ],
)
def test_edit_conversation_request_data(
    request_data, status_code, client_with_user_and_header, accept_json
):
    client, user, session_header, _ = client_with_user_and_header

    conversation = ConversationsFactory(sender_user=user)
    assert Conversations.query.count() == 1, "Make sure we have a single Conversation"

    with mock.patch("flask_jwt_extended.utils.get_current_user", return_value=user):
        url = url_for(
            "conversations.edit_conversation",
            conversation_uuid=conversation.conversation_uuid,
        )

        response = client.put(
            url,
            headers=session_header + accept_json,
            json=request_data,
        )

        assert response.status_code == status_code, str(response.json)

    assert Conversations.query.count() == 1, "Conversations count kept the same."


def test_delete_conversation(client_with_user_and_header, accept_json):
    client, user, session_header, _ = client_with_user_and_header

    conversation = ConversationsFactory(sender_user=user)
    assert conversation.is_marked_deleted is False, "Conversation should be visible"
    assert Conversations.query.count() == 1, "Make sure we have a single Conversation"

    with mock.patch("flask_jwt_extended.utils.get_current_user", return_value=user):
        url = url_for(
            "conversations.delete_conversation",
            conversation_uuid=conversation.conversation_uuid,
        )

        response = client.delete(
            url,
            headers=session_header + accept_json,
        )

        assert response.status_code == 204, str(response.json)

    assert conversation.is_marked_deleted, "Conversation should not be visible"
    assert Conversations.query.count() == 1, "Conversations count kept the same."


def emulate_test_conversation_request_with_error(
    client: FlaskClient,
    user: Users,
    headers: list,
    test_uuid: typing.Union[uuid.UUID, str],
    endpoint_name: str,
):
    with mock.patch("flask_jwt_extended.utils.get_current_user", return_value=user):
        url = url_for(
            endpoint_name,
            conversation_uuid=test_uuid,
        )
        response = client.put(
            url,
            json={"receiver_name": "unbeliever"},
            headers=headers,
        )
        return response


@pytest.mark.integration
def test_conversation_request_without_session(client_with_user_and_header, accept_json):
    client, user, _, _ = client_with_user_and_header
    conversation = ConversationsFactory(sender_user=user)

    endpoints_to_test = [
        "conversations.edit_conversation",
        "conversations.delete_conversation",
    ]
    for endpoint_name in endpoints_to_test:
        response = emulate_test_conversation_request_with_error(
            client, user, accept_json, conversation.conversation_uuid, endpoint_name
        )

        assert response.status_code == 400, "Missing session header"


@pytest.mark.integration
def test_conversation_request_invalid_uuid(client_with_user_and_header, accept_json):
    client, user, session_header, _ = client_with_user_and_header

    headers = session_header + accept_json
    endpoints_to_test = [
        "conversations.edit_conversation",
        "conversations.delete_conversation",
    ]
    for endpoint in endpoints_to_test:
        response = emulate_test_conversation_request_with_error(
            client, user, headers, "invalid uuid", endpoint
        )

        assert response.status_code == 400, "Invalid convo UUID provided"


@pytest.mark.integration
def test_conversation_request_not_found(client_with_user_and_header, accept_json):
    client, user, session_header, _ = client_with_user_and_header
    conversation = ConversationsFactory(sender_user=user)
    wrong_convo_uuid = faker.uuid4()
    assert conversation.conversation_uuid != wrong_convo_uuid

    headers = session_header + accept_json
    endpoints_to_test = [
        "conversations.edit_conversation",
        "conversations.delete_conversation",
    ]
    for endpoint in endpoints_to_test:
        response = emulate_test_conversation_request_with_error(
            client, user, headers, wrong_convo_uuid, endpoint
        )

        assert response.status_code == 404, "Convo with this UUID should not be found"


@pytest.mark.integration
def test_conversation_request_forbidden(client_with_user_and_header, accept_json):
    client, user, session_header, _ = client_with_user_and_header
    conversation = ConversationsFactory()
    assert user.user_uuid != conversation.sender_user_uuid, "Users should be different"

    headers = session_header + accept_json
    endpoints_to_test = [
        "conversations.edit_conversation",
        "conversations.delete_conversation",
    ]
    for endpoint in endpoints_to_test:
        response = emulate_test_conversation_request_with_error(
            client, user, headers, conversation.conversation_uuid, endpoint
        )

        assert response.status_code == 403, "Convo sender_user mismatch"


@pytest.mark.integration
def test_conversation_request_unauthorized(client_with_user_and_header, accept_json):
    client, user, session_header, _ = client_with_user_and_header
    client.delete_cookie("localhost", "access_token")

    conversation = ConversationsFactory(sender_user=user)

    headers = session_header + accept_json
    endpoints_to_test = [
        "conversations.edit_conversation",
        "conversations.delete_conversation",
    ]
    for endpoint in endpoints_to_test:
        response = emulate_test_conversation_request_with_error(
            client, user, headers, conversation.conversation_uuid, endpoint
        )

        assert response.status_code == 401, "Unauthorized access forbidden"


@pytest.mark.integration
def test_get_conversations_empty(client_with_user_and_header, accept_json):
    client, _, session_header, _ = client_with_user_and_header
    url = url_for("conversations.get_conversations")
    response = client.get(
        url,
        headers=session_header + accept_json,
    )
    assert response.status_code == 200, str(response.json)
    assert response.json == {"conversations": []}


@pytest.mark.parametrize(
    "invited_user_name",
    [
        "",
        "managementmanagementm",
        "managementmanagementmanagementmanagementmanagementm",
    ],
)
@pytest.mark.integration
def test_create_conversation_with_invalid_invitee(
    invited_user_name, client_with_user_and_header, accept_json
):
    client, _, session_header, _ = client_with_user_and_header
    url = url_for("conversations.create_conversation_invite")
    response = client.post(
        url,
        headers=session_header + accept_json,
        json={"invitedUserName": invited_user_name},
    )
    assert (
        response.status_code == 400
    ), "Must provide a JSON body with the name of the invited user."


@pytest.mark.integration
def test_create_conversation_with_invalid_session(
    client_with_user_and_header, accept_json
):
    client, _, session_header, _ = client_with_user_and_header
    url = url_for("conversations.create_conversation_invite")
    bad_session_header = [("X-Session-Id", faker.uuid4().upper())]
    assert bad_session_header != session_header
    response = client.post(
        url,
        headers=bad_session_header + accept_json,
        json={"invitedUserName": faker.name()},
    )
    assert response.status_code == 404, "SESSION_UUID is not in the db."


@pytest.mark.integration
def test_create_conversation_successful(client_with_user_and_header, accept_json):
    client, _, session_header, _ = client_with_user_and_header
    url = url_for("conversations.create_conversation_invite")
    response = client.post(
        url,
        headers=session_header + accept_json,
        json={"invitedUserName": faker.name()},
    )
    assert response.status_code == 201, str(response.json)
    assert (
        response.json["message"] == "conversation created"
    ), 'Successful creation should give "conversation created" message.'
    assert (
        response.json["conversationId"] == response.json["conversationId"].lower()
    ), "conversationId uuid should be lower case"
    assert is_uuid(
        response.json["conversationId"]
    ), "conversationId is not a valid uuid"
