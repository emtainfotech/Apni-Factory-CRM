import requests
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

SPRINTVERIFY_URL = "https://uat.paysprint.in/sprintverify-uat/api/v1/verification/gst-advance-v2"

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0aW1lc3RhbXAiOjE3Njk3NTc3NTUsInBhcnRuZXJJZCI6IkNPUlAwMDAwMjM3MCIsInJlcWlkIjo5ODk2ODIwfQ.p6ZYoTDWnvlaTRANT75glwI8GMOi7hk6ox0AFN_xcuc"
AUTHORISED_KEY = "TVRJek5EVTJOelUwTnpKRFQxSlFNREF3TURFPQ=="
USER_AGENT = "CORP00002370"


@csrf_exempt
def gst_verify_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    try:
        body = json.loads(request.body)

        gst_number = body.get("gst_number")
        refid = body.get("refid", "765757555")

        if not gst_number:
            return JsonResponse({"error": "gst_number is required"}, status=400)

        headers = {
            "Token": TOKEN,
            "authorisedkey": AUTHORISED_KEY,
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json"
        }

        payload = {
            "refid": refid,
            "gst_number": gst_number
        }

        response = requests.post(SPRINTVERIFY_URL, json=payload, headers=headers, timeout=15)

        return JsonResponse(response.json(), safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

