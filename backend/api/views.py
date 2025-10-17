from rest_framework.response import Response
from rest_framework.views import APIView

class PingView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"ok": True})
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

class SecurePingView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response({"ok": True, "user": str(request.user)})
