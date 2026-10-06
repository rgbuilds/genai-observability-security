"""Build canary inventories from registered specs."""

from genai_observability.full_study.references import FullStudyCanaryInventory
from genai_observability.grading.references import EligibleCanary


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


def all_tokens(inventories: list[FullStudyCanaryInventory]) -> dict[str, str]:
    owned: dict[str, str] = {}
    for inventory in inventories:
        for canary in inventory.eligible_canaries:
            if canary.eligible:
                owned[canary.token] = inventory.execution_id
    return owned
