"""Testes do próprio ServicoTelemetriaEspacial com a camada de rede (urlopen) mockada."""

import json
import urllib.error
from unittest.mock import MagicMock

import pytest

from src.servico_telemetria import ServicoTelemetriaEspacial, TelemetriaIndisponivelError


@pytest.fixture
def urlopen_mock(mocker):
    resposta = MagicMock()
    resposta.read.return_value = json.dumps({"recebido": True}).encode("utf-8")
    mock = mocker.patch("src.servico_telemetria.urlopen")
    mock.return_value.__enter__.return_value = resposta
    return mock


@pytest.fixture
def servico():
    return ServicoTelemetriaEspacial(url_base="https://terra.example/api/", timeout=3)


def test_enviar_relatorio_faz_post_json(servico, urlopen_mock):
    assert servico.enviar_relatorio_status({"estoque_oxigenio": 480}) == {"recebido": True}

    requisicao = urlopen_mock.call_args.args[0]
    assert requisicao.full_url == "https://terra.example/api/status"
    assert requisicao.get_method() == "POST"
    assert json.loads(requisicao.data) == {"estoque_oxigenio": 480}
    assert urlopen_mock.call_args.kwargs == {"timeout": 3}


def test_disparar_alerta_envia_prioridade_maxima(servico, urlopen_mock):
    servico.disparar_alerta_crise("OXIGENIO_INSUFICIENTE", "vazamento no módulo B")

    requisicao = urlopen_mock.call_args.args[0]
    assert requisicao.full_url == "https://terra.example/api/alertas"
    assert json.loads(requisicao.data) == {
        "codigo": "OXIGENIO_INSUFICIENTE",
        "mensagem": "vazamento no módulo B",
        "prioridade": "MAXIMA",
    }


def test_resposta_vazia_retorna_dicionario_vazio(servico, urlopen_mock):
    urlopen_mock.return_value.__enter__.return_value.read.return_value = b""
    assert servico.enviar_relatorio_status({}) == {}


@pytest.mark.parametrize(
    "erro", [urllib.error.URLError("sem rota"), TimeoutError("timeout"), urllib.error.HTTPError("u", 503, "x", {}, None)]
)
def test_falhas_de_rede_viram_telemetria_indisponivel(servico, mocker, erro):
    mocker.patch("src.servico_telemetria.urlopen", side_effect=erro)
    with pytest.raises(TelemetriaIndisponivelError, match="inacessível"):
        servico.disparar_alerta_crise("X", "y")


def test_rede_real_e_bloqueada_na_suite():
    """Garante que a fixture autouse `bloquear_rede` impede chamadas reais."""
    with pytest.raises(AssertionError, match="rede real"):
        ServicoTelemetriaEspacial().enviar_relatorio_status({})
