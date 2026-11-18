"""Testes E2E do painel.html com Selenium WebDriver (Chrome headless).

Toda sincronização usa esperas explícitas (WebDriverWait + expected_conditions);
não há time.sleep() nesta suíte.
"""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from tests.conftest import salvar_screenshot

pytestmark = pytest.mark.e2e

TIMEOUT = 10


class PainelControleWeb:
    """Page Object do painel ECLSS."""

    NIVEL_OXIGENIO = (By.ID, "nivel-oxigenio")
    NIVEL_AGUA = (By.ID, "nivel-agua")
    AUTONOMIA = (By.ID, "dias-autonomia")
    STATUS = (By.ID, "status-habitat")
    CAMPO_ASTRONAUTA = (By.ID, "astronauta")
    CAMPO_QUANTIDADE = (By.ID, "quantidade")
    BOTAO_SOLICITAR = (By.ID, "btn-solicitar")
    PROCESSANDO = (By.ID, "processando")
    MENSAGEM = (By.ID, "mensagem")
    ALERTA_CRISE = (By.ID, "alerta-crise")
    ITENS_HISTORICO = (By.CSS_SELECTOR, "#historico li")

    def __init__(self, driver, url):
        self.driver = driver
        self.url = url
        self.espera = WebDriverWait(driver, TIMEOUT)

    def abrir(self):
        self.driver.get(self.url)
        self.espera.until(EC.visibility_of_element_located(self.NIVEL_OXIGENIO))
        return self

    def texto(self, localizador):
        return self.driver.find_element(*localizador).text

    def solicitar_oxigenio(self, astronauta, quantidade):
        self.espera.until(EC.element_to_be_clickable(self.BOTAO_SOLICITAR))
        campo_astronauta = self.driver.find_element(*self.CAMPO_ASTRONAUTA)
        campo_astronauta.clear()
        campo_astronauta.send_keys(astronauta)
        campo_quantidade = self.driver.find_element(*self.CAMPO_QUANTIDADE)
        campo_quantidade.clear()
        campo_quantidade.send_keys(str(quantidade))
        self.driver.find_element(*self.BOTAO_SOLICITAR).click()

    def aguardar_resposta(self):
        """Espera o processamento assíncrono terminar e devolve o texto da mensagem."""
        self.espera.until(EC.visibility_of_element_located(self.MENSAGEM))
        self.espera.until(EC.invisibility_of_element_located(self.PROCESSANDO))
        return self.texto(self.MENSAGEM)

    def aguardar_nivel_oxigenio(self, valor_esperado):
        self.espera.until(EC.text_to_be_present_in_element(self.NIVEL_OXIGENIO, valor_esperado))


@pytest.fixture
def painel(driver, url_painel):
    return PainelControleWeb(driver, url_painel).abrir()


def test_painel_exibe_niveis_iniciais(painel):
    assert painel.driver.title == "Painel ECLSS - Habitat Marte"
    assert painel.texto(painel.NIVEL_OXIGENIO) == "500.00"
    assert painel.texto(painel.NIVEL_AGUA) == "2000.00"
    assert painel.texto(painel.AUTONOMIA) == "95.2"
    assert painel.texto(painel.STATUS) == "NORMAL"


def test_solicitacao_aprovada_atualiza_nivel_no_dom(painel):
    painel.solicitar_oxigenio("Silva", 25)

    # O botão fica desabilitado durante a transmissão.
    painel.espera.until(EC.visibility_of_element_located(painel.PROCESSANDO))
    assert not painel.driver.find_element(*painel.BOTAO_SOLICITAR).is_enabled()

    painel.aguardar_nivel_oxigenio("475.00")
    assert painel.aguardar_resposta() == "Aprovado: 25.00 kg liberados para Silva."
    assert [li.text for li in painel.driver.find_elements(*painel.ITENS_HISTORICO)] == ["Silva: 25.00 kg"]
    assert not painel.driver.find_element(*painel.ALERTA_CRISE).is_displayed()


def test_solicitacoes_sequenciais_acumulam(painel):
    painel.solicitar_oxigenio("Silva", 100)
    painel.aguardar_nivel_oxigenio("400.00")
    painel.solicitar_oxigenio("Costa", 50.5)
    painel.aguardar_nivel_oxigenio("349.50")

    painel.espera.until(lambda d: len(d.find_elements(*PainelControleWeb.ITENS_HISTORICO)) == 2)
    assert painel.texto(painel.STATUS) == "NORMAL"


def test_solicitacao_acima_da_reserva_e_negada_com_alerta(painel):
    painel.solicitar_oxigenio("Costa", 450)

    alerta = painel.espera.until(EC.visibility_of_element_located(painel.ALERTA_CRISE))
    assert "excede o estoque seguro" in alerta.text
    assert painel.aguardar_resposta().startswith("Negado: oxigênio insuficiente")
    assert painel.texto(painel.NIVEL_OXIGENIO) == "500.00"
    assert painel.driver.find_elements(*painel.ITENS_HISTORICO) == []


def test_status_muda_para_alerta_quando_autonomia_cai(painel):
    painel.solicitar_oxigenio("Souza", 380)

    painel.espera.until(EC.text_to_be_present_in_element(painel.STATUS, "ALERTA"))
    assert painel.texto(painel.AUTONOMIA) == "23.8"
    assert "autonomia do habitat reduzida" in painel.texto(painel.ALERTA_CRISE)


@pytest.mark.parametrize(
    "astronauta, quantidade, mensagem_esperada",
    [
        ("", 10, "Erro: informe a identificação do astronauta."),
        ("Silva", 0, "Erro: a quantidade deve ser maior que zero."),
        ("Silva", -5, "Erro: a quantidade deve ser maior que zero."),
    ],
)
def test_validacao_do_formulario(painel, astronauta, quantidade, mensagem_esperada):
    painel.solicitar_oxigenio(astronauta, quantidade)
    assert painel.aguardar_resposta() == mensagem_esperada
    assert painel.texto(painel.NIVEL_OXIGENIO) == "500.00"


def test_captura_de_evidencia_visual(painel):
    """Valida o mecanismo de evidência usado automaticamente quando um teste falha."""
    caminho = salvar_screenshot(painel.driver, "evidencia_painel")
    try:
        assert caminho.exists()
        assert caminho.read_bytes().startswith(b"\x89PNG")
    finally:
        caminho.unlink(missing_ok=True)
