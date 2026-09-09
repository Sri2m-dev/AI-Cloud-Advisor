"""Integrated, conservative document-intelligence product view for PUE-011 closure."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from universal_evidence.containers.pdf import decompose_pdf
from universal_evidence.containers.xlsx import decompose_xlsx
from universal_evidence.entitlements import analyze_entitlement_evidence
from universal_evidence.financial.adapters import analyze_decomposition_financial
from universal_evidence.identity import deduplicate_documents, identity_candidates
from universal_evidence.semantics import classify_decomposition, group_evidence_sets


@dataclass(frozen=True, slots=True)
class DocumentResult:
    filename: str
    container_type: str
    region_count: int
    evidence_set_count: int
    financial_representation_count: int
    purchased_licenses: int
    assigned_licenses: int
    unassigned_licenses: int
    access_entitlements: int
    provenance: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductClosureResult:
    documents: tuple[DocumentResult, ...]
    representation_count: int
    business_document_count: int
    purchased_licenses: int
    assigned_licenses: int
    unassigned_licenses: int
    access_entitlements: int
    currency_state: str
    savings_state: str
    unknowns: tuple[str, ...]
    financial_documents: tuple[dict, ...]

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, payload):
        return cls(
            tuple(
                DocumentResult(
                    **{
                        **item,
                        "provenance": tuple(item["provenance"]),
                        "warnings": tuple(item["warnings"]),
                    }
                )
                for item in payload["documents"]
            ),
            int(payload["representation_count"]),
            int(payload["business_document_count"]),
            int(payload["purchased_licenses"]),
            int(payload["assigned_licenses"]),
            int(payload["unassigned_licenses"]),
            int(payload["access_entitlements"]),
            str(payload["currency_state"]),
            str(payload["savings_state"]),
            tuple(payload["unknowns"]),
            tuple(payload["financial_documents"]),
        )


def analyze_document_bundle(*, context, files: tuple[tuple[str, bytes], ...]):
    """Run C-H over one authorized bundle without promoting unresolved facts."""
    results = []
    candidates = []
    financial_details = []
    purchased = assigned = unassigned = access = 0
    for filename, content in files:
        suffix = Path(filename).suffix.casefold()
        if suffix not in {".xlsx", ".pdf"}:
            continue
        kwargs = dict(
            context=context,
            content=content,
            admitted_at=datetime.now(timezone.utc),
            source_reference=f"authorized-upload:{filename}",
            filename=filename,
        )
        decomposition = decompose_xlsx(**kwargs) if suffix == ".xlsx" else decompose_pdf(**kwargs)
        classifications = classify_decomposition(decomposition)
        evidence_sets = group_evidence_sets(decomposition.regions, classifications)
        adapted = analyze_decomposition_financial(
            decomposition=decomposition,
            classifications=classifications,
            evidence_sets=evidence_sets,
            content=content,
        )
        document_candidates = identity_candidates(
            decomposition=decomposition, adapted_documents=adapted
        )
        candidates.extend(document_candidates)
        entitlement = analyze_entitlement_evidence(
            decomposition=decomposition,
            classifications=classifications,
            evidence_sets=evidence_sets,
            content=content,
        )
        purchased += entitlement.purchased_license_quantity
        assigned += entitlement.assigned_license_quantity
        unassigned += entitlement.unassigned_license_quantity
        access += entitlement.access_entitlement_quantity
        for item, identity in zip(adapted, document_candidates, strict=True):
            analysis = item.analysis
            financial_details.append(
                {
                    "filename": filename,
                    "representation_id": identity.representation.representation_id,
                    "detail_total": str(analysis.eligible_detail_total)
                    if analysis.eligible_detail_total is not None
                    else None,
                    "tax": str(analysis.tax_total) if analysis.tax_total is not None else None,
                    "total_due": str(analysis.gross_payable)
                    if analysis.gross_payable is not None
                    else None,
                    "currencies": list(analysis.currency.currencies),
                    "currency_governed": analysis.currency.governed,
                    "reconciliations": [item.state.value for item in analysis.reconciliations],
                    "provenance": [value.reference for value in item.evidence.values]
                    + [line.row_reference for line in item.evidence.lines],
                }
            )
        results.append(
            DocumentResult(
                filename,
                decomposition.container.container_type,
                len(decomposition.regions),
                len(evidence_sets),
                len(adapted),
                entitlement.purchased_license_quantity,
                entitlement.assigned_license_quantity,
                entitlement.unassigned_license_quantity,
                entitlement.access_entitlement_quantity,
                tuple(region.lineage.physical_locator for region in decomposition.regions),
                tuple(decomposition.warnings),
            )
        )
    view = deduplicate_documents(tuple(candidates))
    business_identity = {
        representation_id: group.business_document_fingerprint
        for group in view.groups
        for representation_id in group.representation_ids
    }
    financial_details = [
        {
            **item,
            "business_document_id": business_identity[item["representation_id"]],
        }
        for item in financial_details
    ]
    currencies = {
        currency
        for item in financial_details
        for currency in item["currencies"]
        if item["currency_governed"]
    }
    currency_state = next(iter(currencies)) if len(currencies) == 1 else "UNRESOLVED"
    return ProductClosureResult(
        tuple(results),
        view.representation_count,
        view.business_document_count,
        purchased,
        assigned,
        unassigned,
        access,
        currency_state,
        "INSUFFICIENT_EVIDENCE",
        ("owner", "application", "cost center")
        + (("currency",) if currency_state == "UNRESOLVED" else ()),
        tuple(financial_details),
    )


def answer_document_question(question: str, result: ProductClosureResult):
    """Answer the supported closure questions with explicit source references."""
    text = question.casefold()
    provenance = tuple(
        reference for document in result.documents for reference in document.provenance[:3]
    )
    if "currency" in text:
        answer = (
            "Currency is UNKNOWN/UNRESOLVED because the evidence does not establish one "
            "governed ISO currency."
            if result.currency_state == "UNRESOLVED"
            else f"The governed evidence currency is {result.currency_state}."
        )
    elif "unassigned" in text:
        answer = f"The governed evidence shows {result.unassigned_licenses} unassigned licenses."
    elif "assigned" in text:
        answer = f"The governed evidence shows {result.assigned_licenses} assigned licenses."
    elif "purchased" in text:
        answer = f"The governed evidence shows {result.purchased_licenses} purchased licenses."
    elif "access" in text:
        answer = f"The governed evidence shows {result.access_entitlements} access entitlements."
    elif "license" in text or "entitlement" in text:
        answer = (
            f"The governed evidence shows {result.purchased_licenses} purchased licenses, "
            f"{result.assigned_licenses} assigned, {result.unassigned_licenses} unassigned, "
            f"and {result.access_entitlements} access entitlements."
        )
    elif "invoice" in text or "document" in text or "duplicate" in text:
        answer = (
            f"Nexora found {result.representation_count} invoice representations grouped into "
            f"{result.business_document_count} business documents across "
            f"{len(result.documents)} files."
        )
    elif "spend" in text or "cost" in text or "amount" in text or "total" in text:
        answer = (
            "A cross-document monetary total is UNKNOWN because a single governed currency "
            "authority is unavailable. Nexora has not converted or summed incompatible evidence."
            if result.currency_state == "UNRESOLVED"
            else "Document financial controls are available in the evidence workspace."
        )
    elif any(item in text for item in ("owner", "application", "cost center", "cost centre")):
        answer = "UNKNOWN — the uploaded evidence does not establish that governed relationship."
    elif "saving" in text or "opportunity" in text:
        answer = (
            "Savings are UNKNOWN: optimization eligibility and governed pricing "
            "are not established."
        )
    else:
        answer = (
            "Nexora cannot certify that answer from this document workspace; "
            "the result remains UNKNOWN."
        )
    return answer, provenance
