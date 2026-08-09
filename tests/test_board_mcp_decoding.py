from sourcecut_api.services.board import _hash_text


def test_mcp_bytes_literal_hash_is_normalized() -> None:
    digest = "a" * 64

    assert _hash_text(digest.encode()) == digest
    assert _hash_text(f"b'{digest}'") == digest
    assert _hash_text(digest) == digest
