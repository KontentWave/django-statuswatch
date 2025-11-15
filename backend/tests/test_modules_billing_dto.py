from modules.billing import (
    BillingCancelResponseDto,
    BillingCheckoutResponseDto,
    BillingPortalResponseDto,
    compact_payload,
)


def test_checkout_response_compacts_payload():
    dto = BillingCheckoutResponseDto(url="https://stripe.example")

    assert dto.to_dict() == {"url": "https://stripe.example"}


def test_portal_response_preserves_error_fields():
    dto = BillingPortalResponseDto(detail="Portal not ready", error="retry")

    assert dto.to_dict() == {"detail": "Portal not ready", "error": "retry"}


def test_cancel_response_includes_plan():
    dto = BillingCancelResponseDto(plan="free")

    assert dto.to_dict() == {"plan": "free"}


def test_compact_payload_filters_none_values():
    payload = {"url": None, "detail": "something", "error": None}

    assert compact_payload(payload) == {"detail": "something"}
