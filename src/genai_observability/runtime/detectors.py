from genai_observability.patterns.library import PatternLibrary, load_pattern_library
from genai_observability.patterns.scan import PAYLOAD_FIELD_STAGES, scan_payload
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.span import AuthzAttributes, CanonicalSpan, ContentAttributes, DetectorEvent

_CONTENT_FIELDS = (
    ("system", "content.system"),
    ("user", "content.user"),
    ("output", "content.output"),
    ("retrieved", "content.retrieved"),
    ("tool_args", "content.tool_args"),
    ("tool_result", "content.tool_result"),
)
_AUTHZ_FIELDS = (
    ("principal_id", "authz.principal_id"),
    ("roles", "authz.roles"),
    ("resource", "authz.resource"),
)

_DETECTOR_IDS = {
    "canary_grammar": "patternlib.v1.canary_grammar",
    "secret_key": "patternlib.v1.secret_key",
}


def _hits_for_group(group: ContentAttributes | AuthzAttributes | None, fields: tuple[tuple[str, str], ...], library: PatternLibrary) -> list[DetectorEvent]:
    if group is None:
        return []
    events: dict[tuple[str, str], DetectorEvent] = {}
    for attr, field_name in fields:
        value = getattr(group, attr)
        if value is None:
            continue
        stage = PAYLOAD_FIELD_STAGES[field_name]
        for hit in scan_payload(value, stage, library):
            key = (hit.stage.value, hit.match_class)
            events[key] = DetectorEvent(
                detector_id=_DETECTOR_IDS[hit.match_class],
                category=library.canary_grammar.category
                if hit.match_class == "canary_grammar"
                else library.secret_keys.category,
                stage=hit.stage,
                match_class=hit.match_class,
            )
    return list(events.values())


def _span_detector_events(span: CanonicalSpan, library: PatternLibrary) -> list[DetectorEvent]:
    events = _hits_for_group(span.content, _CONTENT_FIELDS, library)
    events.extend(_hits_for_group(span.authz, _AUTHZ_FIELDS, library))
    events.sort(key=lambda event: (event.stage.value, event.match_class))
    return events


def apply_runtime_detectors(
    stream: CanonicalEventStream,
    library: PatternLibrary | None = None,
) -> CanonicalEventStream:
    """Return a copy with detector events recomputed from payload fields.

    Replaces fixture-supplied detector_events. Does not mutate `stream`.
    """
    library = library or load_pattern_library()
    spans = [
        span.model_copy(update={"detector_events": _span_detector_events(span, library)})
        for span in stream.spans
    ]
    return stream.model_copy(update={"spans": spans})
