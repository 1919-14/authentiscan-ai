import json

from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.http import JsonResponse, StreamingHttpResponse

from common.llm import LLMConfigurationError, LLMRequestError, chat_completion, is_configured, stream_response
from detector.models import ScanResult

from .models import ChatMessage, ChatSession

SYSTEM_PROMPT = (
    "You are the AuthentiScan AI Assistant, embedded in a college project that "
    "detects likely AI-generated or manipulated images using Error Level Analysis, "
    "noise-consistency analysis, and EXIF metadata heuristics. Answer questions about "
    "image forensics, deepfakes, AI-generated content detection, and this specific "
    "scan's results (if given). Keep answers concise, friendly, and technically honest. "
    "If asked something unrelated to the app or image forensics, answer briefly and "
    "steer back to what the tool can help with."
)


def _build_messages(session):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if session.scan:
        scan = session.scan
        messages.append({
            "role": "system",
            "content": (
                f"Context: the user is discussing scan {scan.id}. "
                f"Verdict: {scan.get_verdict_display()}. "
                f"AI-generation likelihood: {scan.ai_likelihood}%. "
                f"ELA score: {scan.ela_score}, noise score: {scan.noise_score}, "
                f"metadata score: {scan.metadata_score}."
            ),
        })

    history = list(session.messages.order_by("created_at"))
    for msg in history[-12:]:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})
    return messages


def chat_page(request):
    """Renders the chat interface. Optionally scoped to a scan via ?scan=<uuid>."""
    scan = None
    scan_id = request.GET.get("scan")
    if scan_id:
        scan = ScanResult.objects.filter(id=scan_id).first()

    session = ChatSession.objects.create(scan=scan)

    return render(request, "chatbot/chat.html", {
        "session": session,
        "scan": scan,
        "llm_configured": is_configured(),
    })


@require_POST
def send_message(request, session_id):
    """AJAX endpoint: accept a user message, return the assistant's reply as JSON."""
    session = get_object_or_404(ChatSession, id=session_id)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request body."}, status=400)

    user_text = (payload.get("message") or "").strip()
    if not user_text:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)
    if len(user_text) > 2000:
        return JsonResponse({"error": "Message is too long (max 2000 characters)."}, status=400)

    ChatMessage.objects.create(session=session, role="user", content=user_text)

    messages = _build_messages(session)

    try:
        reply = chat_completion(messages=messages, temperature=0.5, max_tokens=500)
    except (LLMConfigurationError, LLMRequestError) as exc:
        reply = (
            "I can't reach the AI assistant right now. "
            f"({exc}) Please check your OPENCODE_API_KEY in the .env file."
        )

    ChatMessage.objects.create(session=session, role="assistant", content=reply)

    return JsonResponse({"reply": reply})


@require_POST
def send_message_stream(request, session_id):
    """SSE streaming endpoint for the chat assistant."""
    session = get_object_or_404(ChatSession, id=session_id)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request body."}, status=400)

    user_text = (payload.get("message") or "").strip()
    if not user_text:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)
    if len(user_text) > 2000:
        return JsonResponse({"error": "Message is too long (max 2000 characters)."}, status=400)

    ChatMessage.objects.create(session=session, role="user", content=user_text)

    messages = _build_messages(session)

    response = StreamingHttpResponse(
        streaming_content=stream_response(messages, temperature=0.5, max_tokens=20000),
        content_type="text/event-stream",
    )
    response["X-Accel-Buffering"] = "no"
    response["Cache-Control"] = "no-cache"
    return response
