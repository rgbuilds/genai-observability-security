"""Predicted retention credits from the allowlist. Not live-capture lessons."""

from genai_observability.full_study.questions import FULL_STUDY_QUESTION_IDS
from genai_observability.full_study.references import FullStudyAnswerManifest
from genai_observability.full_study.select import _first_retrieved, _fs16_loc2, _last_output
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import PolicyId, SpanKind

CONTENT_FACTS = frozenset({"FS12", "FS13", "FS14", "FS15", "FS16", "OC1"})
P3_ONLY_SECURITY = frozenset({"FS8", "FS9", "FS10"})
METADATA_ALWAYS = frozenset({"FS1", "FS2", "FS3", "FS5", "FS6", "FS7"})


def _has_in_grammar_token(manifest: FullStudyAnswerManifest, question_id: str) -> bool:
    reference = manifest.question(question_id)
    token = reference.token or (reference.answer if isinstance(reference.answer, str) else None)
    return bool(token) and str(token).startswith("SYNTH-")


def _stream_text_has_canary(*texts: str | None) -> bool:
    return any(text and "SYNTH-" in text for text in texts)


def _tool_args_contain_canary(stream: CanonicalEventStream) -> bool:
    for span in stream.spans:
        if span.kind is not SpanKind.TOOL or span.content is None:
            continue
        args = span.content.tool_args
        if args is not None and "SYNTH-" in str(args):
            return True
    return False


def predict_credit(
    question_id: str,
    policy_id: PolicyId,
    stream: CanonicalEventStream,
    manifest: FullStudyAnswerManifest,
) -> int | None:
    reference = manifest.question(question_id)
    if not reference.applicable:
        return None
    if question_id in METADATA_ALWAYS:
        return 1
    if question_id == "FS4":
        return 0 if policy_id is PolicyId.P0 else 1
    if question_id in P3_ONLY_SECURITY:
        return 1 if policy_id is PolicyId.P3 else 0
    if question_id == "FS11":
        return 0 if policy_id is PolicyId.P0 else 1
    if question_id in {"FS16", "OC1"}:
        if policy_id is PolicyId.P1:
            return 1
        if policy_id is PolicyId.P2:
            loc1 = _first_retrieved(stream)
            loc2 = _last_output(stream) if question_id == "OC1" else _fs16_loc2(stream)
            if _stream_text_has_canary(loc1, loc2):
                return 0
            return 1
        return 0
    if question_id == "FS12":
        if policy_id is PolicyId.P1:
            return 1
        if policy_id is PolicyId.P2:
            return 0 if _tool_args_contain_canary(stream) else 1
        return 0
    if question_id == "FS13":
        return 1 if policy_id in {PolicyId.P1, PolicyId.P2} else 0
    if question_id in {"FS14", "FS15"}:
        if policy_id is PolicyId.P1:
            return 1
        if policy_id is PolicyId.P2 and not _has_in_grammar_token(manifest, question_id):
            return 1
        return 0
    raise KeyError(question_id)


def predict_table(stream: CanonicalEventStream, manifest: FullStudyAnswerManifest) -> dict[str, dict[str, int | None]]:
    table: dict[str, dict[str, int | None]] = {}
    for policy_id in PolicyId:
        table[policy_id.value] = {
            question_id: predict_credit(question_id, policy_id, stream, manifest)
            for question_id in FULL_STUDY_QUESTION_IDS
        }
    return table
