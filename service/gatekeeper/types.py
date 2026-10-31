"""Typed shapes for the tool inputs that were bare `list[dict]` in v1.

Agents used to see "array of object" with no field names, which is why `add_evidence` was the most rejected tool
(91 malformed calls before run 4). These give the MCP and OpenAPI schemas real field names, enums and required flags.
The rules in core.py still validate every value; this only makes the contract visible and catches shape errors early.
"""

from __future__ import annotations

from typing import Literal, NotRequired, Union

from pydantic import ConfigDict
from typing_extensions import TypedDict

Confidence = Literal["low", "medium", "high"]
AcquisitionPath = Literal["hire", "partner", "buy", "build", "none"]


class SourceClaim(TypedDict):
    """A fact read from a source. Quote the passage that states it."""
    kind: Literal["source"]
    field: str            # what the claim supports, e.g. "business_case" or "why_now"
    statement: str        # the fact, in your words
    url: str              # a page you actually read
    retrieved_at: str     # ISO date, e.g. 2026-10-28
    excerpt: str          # the passage that states it
    value: NotRequired[Union[str, int, float, None]]


class EstimateClaim(TypedDict):
    """A figure you are estimating. Say how."""
    kind: Literal["estimate"]
    field: str
    statement: str
    confidence: Confidence
    basis: str            # how the estimate was reached
    value: NotRequired[Union[str, int, float, None]]


Claim = Union[SourceClaim, EstimateClaim]


class BacklogVerdict(TypedDict):
    """One backlog item judged against an idea."""
    item_id: int                                                            # an id returned by find_backlog_matches
    verdict: Literal["done", "in_flight", "pull_forward", "related", "unrelated"]
    reason: str                                                             # one plain sentence


class Gap(TypedDict):
    capability: str
    acquisition_path: AcquisitionPath   # "none" caps capability at 0.5 and is recorded as a constraint on the review


class Dependency(TypedDict):
    """Known keys are typed; extra notes (crowding_source, ours_to_build_reason, ...) are allowed and kept."""
    __pydantic_config__ = ConfigDict(extra="allow")  # type: ignore[misc]
    ours_to_build: NotRequired[bool]
    crowding: NotRequired[str]            # low, medium or high, optionally with a short note
    incumbent_curve: NotRequired[Literal["emergence", "growth", "saturation", "unknown"]]
    limiting_factor: NotRequired[Literal["regulation", "channel", "hardware", "software", "other"]]


class FirstCheck(TypedDict):
    smallest_commitment: str
    uncertainty_retired: str
    what_must_be_true: str


class ReadinessDim(TypedDict):
    score: Literal[0, 1, 2, 3]   # 0 absent, 1 asserted, 2 evidenced, 3 validated
    gap: NotRequired[str]        # required below 3: what is missing and where it would come from
    claim_ids: NotRequired[list[int]]
    owner_hint: NotRequired[str]


class Readiness(TypedDict, total=False):
    business_case: ReadinessDim
    product_desc: ReadinessDim
    design_docs: ReadinessDim
    resource_plan: ReadinessDim
    investment_support: ReadinessDim
    prototype: ReadinessDim


# Parameter name -> typed annotation, applied wherever the parameter appears.
OVERRIDES = {
    "claims": list[Claim],
    "verdicts": list[BacklogVerdict],
    "gaps": list[Gap],
    "dependency": Dependency,
    "readiness": Readiness,
    "first_check": FirstCheck,
}
