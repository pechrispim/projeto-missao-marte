"""Serviço de telemetria: comunicação com a estação de controle na Terra.

Esta classe representa uma dependência EXTERNA (rede). Nos testes unitários do
GerenciadorRecursosMarte ela deve ser sempre substituída por dublês (mocks).
"""

import json
import urllib.error
from urllib.request import Request, urlopen


class TelemetriaIndisponivelError(Exception):
    """Falha de comunicação com a estação terrestre."""


class ServicoTelemetriaEspacial:
    URL_PADRAO = "https://controle-missao.terra.example/api/eclss"

    def __init__(self, url_base: str = URL_PADRAO, timeout: float = 10.0):
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout

    def _post(self, endpoint: str, payload: dict) -> dict:
        requisicao = Request(
            url=f"{self.url_base}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(requisicao, timeout=self.timeout) as resposta:
                corpo = resposta.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as erro:
            raise TelemetriaIndisponivelError(
                f"Estação terrestre inacessível: {erro}"
            ) from erro
        return json.loads(corpo) if corpo else {}

    def enviar_relatorio_status(self, relatorio: dict) -> dict:
        """Envia o relatório periódico de status do habitat."""
        return self._post("/status", relatorio)

    def disparar_alerta_crise(self, codigo: str, mensagem: str) -> dict:
        """Dispara um alerta de crise de prioridade máxima para a Terra."""
        return self._post(
            "/alertas",
            {"codigo": codigo, "mensagem": mensagem, "prioridade": "MAXIMA"},
        )
