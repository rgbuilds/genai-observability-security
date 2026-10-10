"""Build canary inventories from registered specs or a realized stream."""

from genai_observability.full_study.references import FullStudyCanaryInventory
from genai_observability.grading.references import EligibleCanary
from genai_observability.schemas.canonical import CanonicalEventStream
from genai_observability.schemas.enums import SpanKind
from genai_observability.serialization import canonical_json_text


def _origin_text(stream: CanonicalEventStream, payload_field: str) -> str:
    parts: list[str] = []
    for span in stream.spans:
        content = span.content
        authz = span.authz
        if payload_field == "content.user" and content is not None and content.user:
            parts.append(content.user)
        elif payload_field == "content.system" and content is not None and content.system:
            parts.append(content.system)
        elif (
            payload_field == "content.retrieved"
            and span.kind is SpanKind.RETRIEVAL
            and content is not None
            and content.retrieved
        ):
            parts.append(content.retrieved)
        elif payload_field == "authz.principal_id" and authz is not None and authz.principal_id:
            parts.append(authz.principal_id)
        elif payload_field == "content.tool_args" and content is not None and content.tool_args is not None:
            parts.append(canonical_json_text(content.tool_args))
        elif payload_field == "content.tool_result" and content is not None and content.tool_result is not None:
            parts.append(canonical_json_text(content.tool_result))
        elif payload_field == "content.output" and content is not None and content.output:
            parts.append(content.output)
    return "\n".join(parts)


def inventory_from_spec(spec: dict) -> FullStudyCanaryInventory:
    plants = []
    for index, plant in enumerate(spec.get("canaries") or [], start=1):
        plants.append(
            EligibleCanary(
                canary_id=f"{plant['location']}-{index}",
                token=plant["token"],
                location=plant["location"],
                payload_field=plant["payload_field"],
                eligible=True,
            )
        )
    return FullStudyCanaryInventory(execution_id=spec["execution_id"], eligible_canaries=plants)


def inventory_from_realized_stream(spec: dict, stream: CanonicalEventStream) -> FullStudyCanaryInventory:
    """Eligible only when the planted token is present in the realized origin field.

    Expected completions are not plants. A token that appears only in model output
    after a live run is not added here unless it was registered as a pre-model plant
    and that origin field still contains it.
    """
    if not isinstance(stream, CanonicalEventStream):
        raise TypeError("inventory_from_realized_stream accepts CanonicalEventStream only")
    plants = []
    for index, plant in enumerate(spec.get("canaries") or [], start=1):
        observed = _origin_text(stream, plant["payload_field"])
        plants.append(
            EligibleCanary(
                canary_id=f"{plant['location']}-{index}",
                token=plant["token"],
                location=plant["location"],
                payload_field=plant["payload_field"],
                eligible=plant["token"] in observed,
            )
        )
    return FullStudyCanaryInventory(
        execution_id=stream.scenario_id,
        eligible_canaries=[item for item in plants if item.eligible],
    )


def all_tokens(inventories: list[FullStudyCanaryInventory]) -> dict[str, str]:
    owned: dict[str, str] = {}
    for inventory in inventories:
        for canary in inventory.eligible_canaries:
            if canary.eligible:
                owned[canary.token] = inventory.execution_id
    return owned
