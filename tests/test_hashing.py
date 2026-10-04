import hashlib

from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.serialization import canonical_hash, canonical_json_bytes, sha256_hex


def test_hash_is_sha256_of_canonical_bytes(sample_stream: CanonicalEventStream) -> None:
    digest = canonical_hash(sample_stream)
    assert digest == sha256_hex(canonical_json_bytes(sample_stream))
    assert digest == hashlib.sha256(canonical_json_bytes(sample_stream)).hexdigest()
    assert len(digest) == 64
    int(digest, 16)


def test_hash_is_stable_across_reload(sample_stream: CanonicalEventStream) -> None:
    again = CanonicalEventStream.model_validate(
        sample_stream.model_dump(mode="json")
    )
    assert canonical_hash(again) == canonical_hash(sample_stream)


def test_hash_changes_when_payload_changes(sample_stream: CanonicalEventStream) -> None:
    mutated = sample_stream.model_copy(update={"request_id": "req-0002"})
    assert canonical_hash(mutated) != canonical_hash(sample_stream)
