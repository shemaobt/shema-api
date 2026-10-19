from tests.facilitator_route_audit_harness import those_that_read


def test_a_door_that_answers_a_redirect_is_not_a_read_to_audit():
    answers = {
        "/sessions/{session_id}/conversation": 200,
        "/sessions/{session_id}/turns/{number}/clip": 307,
    }

    assert those_that_read(answers) == {"/sessions/{session_id}/conversation"}


def test_a_door_named_audio_that_answers_200_is_a_read_to_audit():
    answers = {
        "/sessions/{session_id}/conversation": 200,
        "/sessions/{session_id}/audio": 200,
    }

    assert those_that_read(answers) == {
        "/sessions/{session_id}/conversation",
        "/sessions/{session_id}/audio",
    }
