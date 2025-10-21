from django.http import HttpResponse


def home(request):
    return HttpResponse("Django-01 is running. Try /api/ping/ or /admin/")
