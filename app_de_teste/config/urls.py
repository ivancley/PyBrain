"""Rotas: a tela e as chamadas JSON que ela faz."""

from chat import views
from django.urls import path

urlpatterns = [
    path("", views.tela, name="tela"),
    path("api/mensagem", views.mensagem, name="mensagem"),
    path("api/memorias", views.memorias, name="memorias"),
    path("api/memorias/<str:memoria_id>/historico", views.historico, name="historico"),
    path("api/esquecer", views.esquecer, name="esquecer"),
    path("api/pessoa", views.escolher_pessoa, name="escolher_pessoa"),
]
