"""Tests for the LinkedIn publisher.

Every LinkedIn HTTP call is mocked. These lock down the details that are easy
to get wrong and expensive to discover live: byte-range slicing, ETag
handling, required headers, retryable-vs-permanent classification, and the
rule that a failure returns a PublishResult rather than raising.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.core.publishers.base import PublishResult
from backend.core.publishers.linkedin import LinkedInPublisher

VIDEO_URN = "urn:li:video:C5505AQH-test"
POST_URN = "urn:li:share:7123456789"


@pytest.fixture
def video(tmp_path):
    """A file that passes the local size/format checks."""
    path = tmp_path / "reel.mp4"
    path.write_bytes(b"\x00" * (200 * 1024))  # 200KB, above the 75KB floor
    return path


@pytest.fixture
def publisher():
    return LinkedInPublisher(
        access_token="test-token",
        person_urn="urn:li:person:abc123",
        api_version="202607",
        sleep=lambda _: None,  # never actually wait while polling
    )


def _response(status=200, json_body=None, headers=None):
    response = MagicMock()
    response.status_code = status
    response.headers = headers or {}
    response.json.return_value = json_body if json_body is not None else {}
    response.text = ""
    return response


def _init_body(parts=1):
    """initializeUpload response with `parts` 4MB byte ranges."""
    chunk = 4 * 1024 * 1024
    return {
        "value": {
            "video": VIDEO_URN,
            "uploadToken": "tok" if parts > 1 else "",
            "uploadInstructions": [
                {
                    "uploadUrl": f"https://upload.linkedin.example/part{i}",
                    "firstByte": i * chunk,
                    "lastByte": (i + 1) * chunk - 1,
                }
                for i in range(parts)
            ],
        }
    }


# --------------------------------------------------------------- connection


def test_not_connected_without_token():
    assert not LinkedInPublisher(None, "urn:li:person:x", "202607").is_connected()


def test_not_connected_without_person_urn():
    assert not LinkedInPublisher("token", None, "202607").is_connected()


def test_connected_with_both(publisher):
    assert publisher.is_connected()


def test_publish_without_connection_fails_clearly(video):
    result = LinkedInPublisher(None, None, "202607").publish(video)
    assert not result.success
    assert "not connected" in result.error.lower()
    assert not result.retryable


# --------------------------------------------------------------- validation


def test_rejects_missing_file(publisher, tmp_path):
    ok, error = publisher.validate_media(tmp_path / "nope.mp4")
    assert not ok and "does not exist" in error


def test_rejects_non_mp4(publisher, tmp_path):
    path = tmp_path / "reel.mov"
    path.write_bytes(b"\x00" * (200 * 1024))
    ok, error = publisher.validate_media(path)
    assert not ok and "MP4" in error


def test_rejects_file_below_minimum_size(publisher, tmp_path):
    path = tmp_path / "tiny.mp4"
    path.write_bytes(b"\x00" * 1024)  # 1KB, under the 75KB floor
    ok, error = publisher.validate_media(path)
    assert not ok and "75KB" in error


def test_rejects_file_above_maximum_size(publisher, video):
    with patch.object(Path, "stat") as stat:
        stat.return_value = MagicMock(st_size=600 * 1024 * 1024)
        ok, error = publisher.validate_media(video)
    assert not ok and "500MB" in error


def test_rejects_video_shorter_than_three_seconds(publisher, video):
    with patch.object(publisher, "_probe_duration", return_value=1.5):
        ok, error = publisher.validate_media(video)
    assert not ok and "3 seconds" in error


def test_rejects_video_longer_than_thirty_minutes(publisher, video):
    with patch.object(publisher, "_probe_duration", return_value=31 * 60):
        ok, error = publisher.validate_media(video)
    assert not ok and "30 minutes" in error


def test_accepts_valid_video(publisher, video):
    with patch.object(publisher, "_probe_duration", return_value=30.0):
        ok, error = publisher.validate_media(video)
    assert ok and error == ""


def test_unknown_duration_does_not_block(publisher, video):
    """ffprobe missing must not reject the file - LinkedIn arbitrates instead."""
    with patch.object(publisher, "_probe_duration", return_value=None):
        ok, _ = publisher.validate_media(video)
    assert ok


# ------------------------------------------------------------------ publish


@patch("backend.core.publishers.linkedin.requests")
def test_successful_publish(mock_requests, publisher, video):
    mock_requests.post.side_effect = [
        _response(200, _init_body(parts=1)),          # initializeUpload
        _response(200, {}),                            # finalizeUpload
        _response(201, {}, {"x-restli-id": POST_URN}), # create post
    ]
    mock_requests.put.return_value = _response(200, headers={"etag": '"abc123"'})
    mock_requests.get.return_value = _response(200, {"status": "AVAILABLE"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(video, caption="Hello world")

    assert result.success
    assert result.platform_post_id == POST_URN
    assert POST_URN in result.url


@patch("backend.core.publishers.linkedin.requests")
def test_required_headers_are_sent(mock_requests, publisher, video):
    mock_requests.post.side_effect = [
        _response(200, _init_body()),
        _response(200, {}),
        _response(201, {}, {"x-restli-id": POST_URN}),
    ]
    mock_requests.put.return_value = _response(200, headers={"etag": "abc"})
    mock_requests.get.return_value = _response(200, {"status": "AVAILABLE"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        publisher.publish(video)

    headers = mock_requests.post.call_args_list[0].kwargs["headers"]
    # Omitting either of these produces opaque 400s from LinkedIn.
    assert headers["X-Restli-Protocol-Version"] == "2.0.0"
    assert headers["LinkedIn-Version"] == "202607"
    assert headers["Authorization"] == "Bearer test-token"


@patch("backend.core.publishers.linkedin.requests")
def test_part_upload_omits_authorization_header(mock_requests, publisher, video):
    """Upload URLs are pre-signed; sending our bearer token is rejected."""
    mock_requests.post.side_effect = [
        _response(200, _init_body()),
        _response(200, {}),
        _response(201, {}, {"x-restli-id": POST_URN}),
    ]
    mock_requests.put.return_value = _response(200, headers={"etag": "abc"})
    mock_requests.get.return_value = _response(200, {"status": "AVAILABLE"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        publisher.publish(video)

    put_headers = mock_requests.put.call_args.kwargs["headers"]
    assert "Authorization" not in put_headers
    assert put_headers["Content-Type"] == "application/octet-stream"


@patch("backend.core.publishers.linkedin.requests")
def test_etag_quotes_are_stripped_for_finalize(mock_requests, publisher, video):
    mock_requests.post.side_effect = [
        _response(200, _init_body()),
        _response(200, {}),
        _response(201, {}, {"x-restli-id": POST_URN}),
    ]
    mock_requests.put.return_value = _response(200, headers={"etag": '"quoted-etag"'})
    mock_requests.get.return_value = _response(200, {"status": "AVAILABLE"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        publisher.publish(video)

    finalize_body = mock_requests.post.call_args_list[1].kwargs["json"]
    assert finalize_body["finalizeUploadRequest"]["uploadedPartIds"] == ["quoted-etag"]


@patch("backend.core.publishers.linkedin.requests")
def test_multipart_upload_respects_returned_byte_ranges(mock_requests, publisher, tmp_path):
    """Chunk boundaries must come from the API, never be assumed."""
    chunk = 4 * 1024 * 1024
    path = tmp_path / "big.mp4"
    path.write_bytes(b"A" * chunk + b"B" * 1024)

    mock_requests.post.side_effect = [
        _response(200, _init_body(parts=2)),
        _response(200, {}),
        _response(201, {}, {"x-restli-id": POST_URN}),
    ]
    mock_requests.put.side_effect = [
        _response(200, headers={"etag": "part1"}),
        _response(200, headers={"etag": "part2"}),
    ]
    mock_requests.get.return_value = _response(200, {"status": "AVAILABLE"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(path)

    assert result.success
    first, second = mock_requests.put.call_args_list
    assert first.kwargs["data"] == b"A" * chunk      # exactly the first range
    assert second.kwargs["data"] == b"B" * 1024      # remainder, not padded
    finalize_body = mock_requests.post.call_args_list[1].kwargs["json"]
    assert finalize_body["finalizeUploadRequest"]["uploadedPartIds"] == ["part1", "part2"]


@patch("backend.core.publishers.linkedin.requests")
def test_post_body_references_video_urn(mock_requests, publisher, video):
    mock_requests.post.side_effect = [
        _response(200, _init_body()),
        _response(200, {}),
        _response(201, {}, {"x-restli-id": POST_URN}),
    ]
    mock_requests.put.return_value = _response(200, headers={"etag": "abc"})
    mock_requests.get.return_value = _response(200, {"status": "AVAILABLE"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        publisher.publish(video, caption="My caption")

    body = mock_requests.post.call_args_list[2].kwargs["json"]
    assert body["author"] == "urn:li:person:abc123"
    assert body["commentary"] == "My caption"
    assert body["content"]["media"]["id"] == VIDEO_URN
    assert body["lifecycleState"] == "PUBLISHED"
    assert body["visibility"] == "PUBLIC"


# ------------------------------------------------------------ failure modes


@patch("backend.core.publishers.linkedin.requests")
def test_initialize_failure_is_reported(mock_requests, publisher, video):
    mock_requests.post.return_value = _response(400, {"message": "Bad owner URN"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(video)

    assert not result.success
    assert "Bad owner URN" in result.error
    assert not result.retryable


@patch("backend.core.publishers.linkedin.requests")
def test_server_error_is_marked_retryable(mock_requests, publisher, video):
    mock_requests.post.return_value = _response(503, {"message": "unavailable"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(video)

    assert not result.success
    assert result.retryable


@patch("backend.core.publishers.linkedin.requests")
def test_rate_limit_is_marked_retryable(mock_requests, publisher, video):
    mock_requests.post.return_value = _response(429, {"message": "slow down"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(video)

    assert not result.success
    assert result.retryable


@patch("backend.core.publishers.linkedin.requests")
def test_missing_etag_fails_rather_than_finalizing_garbage(mock_requests, publisher, video):
    mock_requests.post.return_value = _response(200, _init_body())
    mock_requests.put.return_value = _response(200, headers={})  # no ETag

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(video)

    assert not result.success
    assert "ETag" in result.error


@patch("backend.core.publishers.linkedin.requests")
def test_processing_failure_surfaces_linkedin_reason(mock_requests, publisher, video):
    mock_requests.post.side_effect = [
        _response(200, _init_body()),
        _response(200, {}),
    ]
    mock_requests.put.return_value = _response(200, headers={"etag": "abc"})
    mock_requests.get.return_value = _response(
        200, {"status": "PROCESSING_FAILED", "processingFailureReason": "CORRUPT_FILE"}
    )

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(video)

    assert not result.success
    assert "CORRUPT_FILE" in result.error


@patch("backend.core.publishers.linkedin.requests")
def test_polls_until_available(mock_requests, publisher, video):
    mock_requests.post.side_effect = [
        _response(200, _init_body()),
        _response(200, {}),
        _response(201, {}, {"x-restli-id": POST_URN}),
    ]
    mock_requests.put.return_value = _response(200, headers={"etag": "abc"})
    mock_requests.get.side_effect = [
        _response(200, {"status": "PROCESSING"}),
        _response(200, {"status": "PROCESSING"}),
        _response(200, {"status": "AVAILABLE"}),
    ]

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(video)

    assert result.success
    assert mock_requests.get.call_count == 3


@patch("backend.core.publishers.linkedin.requests")
def test_post_accepted_without_id_is_an_error(mock_requests, publisher, video):
    """A 201 with no x-restli-id means we cannot track the post; fail loudly."""
    mock_requests.post.side_effect = [
        _response(200, _init_body()),
        _response(200, {}),
        _response(201, {}, {}),  # header absent
    ]
    mock_requests.put.return_value = _response(200, headers={"etag": "abc"})
    mock_requests.get.return_value = _response(200, {"status": "AVAILABLE"})

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(video)

    assert not result.success
    assert "no post id" in result.error.lower()


@patch("backend.core.publishers.linkedin.requests")
def test_network_error_is_retryable_not_raised(mock_requests, publisher, video):
    import requests as real_requests

    mock_requests.post.side_effect = real_requests.ConnectionError("no route to host")

    with patch.object(publisher, "_probe_duration", return_value=30.0):
        result = publisher.publish(video)

    assert isinstance(result, PublishResult)
    assert not result.success
    assert result.retryable


@patch("backend.core.publishers.linkedin.requests")
def test_invalid_media_never_reaches_the_network(mock_requests, publisher, tmp_path):
    path = tmp_path / "tiny.mp4"
    path.write_bytes(b"\x00" * 100)

    result = publisher.publish(path)

    assert not result.success
    mock_requests.post.assert_not_called()
