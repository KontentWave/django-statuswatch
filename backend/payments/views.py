import stripe
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

@api_view(["GET"])
@permission_classes([AllowAny])
def stripe_config(request):
    return Response({"publicKey": settings.STRIPE_PUBLIC_KEY or ""})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    if not settings.STRIPE_SECRET_KEY:
        return Response({"error": "STRIPE_SECRET_KEY not set"}, status=400)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    amount = int(request.data.get("amount", 2000))  # cents
    currency = request.data.get("currency", "usd")
    name = request.data.get("name", "Test payment")

    domain = request.build_absolute_uri("/").rstrip("/")
    success_url = f"{domain}/?success=true"
    cancel_url  = f"{domain}/?canceled=true"

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": name},
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return Response({"id": session.id, "url": session.url})
    except Exception as e:
        return Response({"error": str(e)}, status=400)
