from src.models import IdentityResult, ProspectInput, Source


def _contains_identity(text: str, prospect: ProspectInput) -> bool:
    normalized = " ".join(text.casefold().split())
    return " ".join(prospect.full_name.casefold().split()) in normalized


def _contains_company(text: str, prospect: ProspectInput) -> bool:
    normalized = " ".join(text.casefold().split())
    company = " ".join(prospect.company_name.casefold().split())
    domain = prospect.company_domain.casefold().removeprefix("www.")
    return bool(company and company in normalized) or bool(
        domain and domain in normalized
    )


def resolve_identity(
    prospect: ProspectInput,
    sources: list[Source],
    model_assessment: dict[str, object] | None = None,
) -> IdentityResult:
    identity_sources = [
        source for source in sources if _contains_identity(source.content, prospect)
    ]
    verified_sources = [
        source
        for source in identity_sources
        if _contains_company(source.content, prospect)
    ]
    if verified_sources:
        return IdentityResult(
            status="verified",
            rationale=(
                "The full prospect name and the supplied company appear together "
                "in a retrieved source."
            ),
            supporting_source_ids=[source.id for source in verified_sources],
        )
    if not identity_sources:
        return IdentityResult(
            status="unverified",
            rationale="No retrieved source directly supports this prospect's identity.",
        )

    assessment = model_assessment or {}
    cited_ids = [
        source.id
        for source in identity_sources
        if source.id in assessment.get("supporting_source_ids", [])
    ]
    proposed = assessment.get("status")
    if proposed == "conflicting" and cited_ids:
        return IdentityResult(
            status="conflicting",
            rationale=str(assessment.get("rationale") or "Sources indicate a different employer."),
            supporting_source_ids=cited_ids,
        )
    return IdentityResult(
        status="ambiguous",
        rationale=(
            str(assessment.get("rationale"))
            if assessment.get("rationale")
            else "A person with this name appears, but the supplied employer is not verified."
        ),
        supporting_source_ids=[
            source.id for source in identity_sources
        ],
    )
