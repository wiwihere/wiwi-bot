from django.contrib import messages
from django.core.management import call_command
from django.shortcuts import redirect


# Create your views here.
def import_dps_report(request):
    call_command("import_dps_report")
    messages.add_message(request, messages.SUCCESS, "Dps report imported.")
    return redirect(request.META.get("HTTP_REFERER"))
