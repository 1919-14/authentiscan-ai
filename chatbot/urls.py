from django.urls import path

from . import views

app_name = "chatbot"

urlpatterns = [
    path("", views.chat_page, name="chat"),
    path("send/<uuid:session_id>/", views.send_message, name="send_message"),
    path("send/<uuid:session_id>/stream/", views.send_message_stream, name="send_message_stream"),
]
