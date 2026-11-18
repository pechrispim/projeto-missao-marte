"""Fixtures compartilhadas da suíte de testes do ECLSS."""

import json
import re
from datetime import datetime
from pathlib import Path

import pytest
from selenium import webdriver

from src import servico_telemetria
from src.gerenciador_recursos import GerenciadorRecursosMarte
from src.servico_telemetria import ServicoTelemetriaEspacial

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
ARQUIVO_PARAMETROS = Path(__file__).resolve().parent / "dados" / "parametros_habitat.json"
PASTA_SCREENSHOTS = RAIZ_PROJETO / "screenshots"


# --------------------------------------------------------------------------- domínio
@pytest.fixture(scope="session")
def parametros_habitat():
    """Fixture GLOBAL (sessão): carrega uma única vez os parâmetros iniciais do habitat."""
    with ARQUIVO_PARAMETROS.open(encoding="utf-8") as arquivo:
        parametros = json.load(arquivo)
    yield parametros
    # Teardown: nenhum teste pode ter alterado os parâmetros compartilhados.
    with ARQUIVO_PARAMETROS.open(encoding="utf-8") as arquivo:
        assert parametros == json.load(arquivo), "parametros_habitat foi modificado por um teste"


@pytest.fixture(autouse=True)
def bloquear_rede(monkeypatch):
    """Rede de segurança: qualquer chamada HTTP real da telemetria falha o teste.

    Testes que precisam simular a rede fazem seu próprio `mocker.patch`
    sobre `urlopen`, que sobrepõe este bloqueio.
    """

    def _urlopen_proibido(*args, **kwargs):
        raise AssertionError("Chamada de rede real detectada durante os testes!")

    monkeypatch.setattr(servico_telemetria, "urlopen", _urlopen_proibido)


@pytest.fixture
def telemetria_mock(mocker):
    """Dublê da telemetria com a mesma assinatura da classe real (autospec)."""
    mock = mocker.create_autospec(ServicoTelemetriaEspacial, instance=True)
    mock.enviar_relatorio_status.return_value = {"recebido": True}
    mock.disparar_alerta_crise.return_value = {"protocolo": "ALERTA-0001"}
    return mock


@pytest.fixture  # escopo function (padrão): instância limpa a cada teste
def gerenciador(parametros_habitat, telemetria_mock):
    """Setup/teardown com yield de um GerenciadorRecursosMarte isolado."""
    instancia = GerenciadorRecursosMarte(**parametros_habitat, telemetria=telemetria_mock)
    yield instancia
    instancia.encerrar()
    assert instancia.historico_solicitacoes == []


# --------------------------------------------------------------------------- Selenium
@pytest.hookimpl(tryfirst=True, wrapper=True)
def pytest_runtest_makereport(item, call):
    """Disponibiliza o resultado de cada fase (setup/call/teardown) em `item.rep_<fase>`."""
    relatorio = yield
    setattr(item, f"rep_{relatorio.when}", relatorio)
    return relatorio


def salvar_screenshot(driver, nome_teste: str) -> Path:
    """Salva a evidência visual da tela atual em screenshots/."""
    PASTA_SCREENSHOTS.mkdir(exist_ok=True)
    nome_seguro = re.sub(r"[^\w.-]+", "_", nome_teste)
    caminho = PASTA_SCREENSHOTS / f"{nome_seguro}_{datetime.now():%Y%m%d_%H%M%S_%f}.png"
    driver.save_screenshot(str(caminho))
    return caminho


@pytest.fixture(scope="session")
def url_painel():
    return (RAIZ_PROJETO / "web" / "painel.html").as_uri()


@pytest.fixture
def driver(request):
    """Inicializa o Chrome headless e garante driver.quit() ao final.

    Se a validação do teste falhar, captura automaticamente a tela como evidência.
    """
    opcoes = webdriver.ChromeOptions()
    for argumento in (
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1366,900",
    ):
        opcoes.add_argument(argumento)
    navegador = webdriver.Chrome(options=opcoes)
    yield navegador

    relatorio = getattr(request.node, "rep_call", None)
    if relatorio is not None and relatorio.failed:
        caminho = salvar_screenshot(navegador, request.node.name)
        print(f"\n[evidência] screenshot salva em: {caminho}")
    navegador.quit()
