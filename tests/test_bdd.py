"""Mapeamento dos passos Gherkin (features/solicitacao_oxigenio.feature) com pytest-bdd."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.gerenciador_recursos import (
    GerenciadorRecursosMarte,
    NivelEmergenciaInvalidoError,
    OxigenioInsuficienteError,
)

pytestmark = pytest.mark.bdd

scenarios("features/solicitacao_oxigenio.feature")


@pytest.fixture
def contexto():
    """Estado compartilhado entre os passos de um cenário."""
    return {"resultado": None, "erro": None}


# ----------------------------------------------------------------------------- Given
@given(
    parsers.parse("o habitat possui {oxigenio:d} kg de oxigênio e {agua:d} litros de água"),
    target_fixture="habitat",
)
def habitat(parametros_habitat, telemetria_mock, oxigenio, agua):
    return GerenciadorRecursosMarte(
        **{**parametros_habitat, "estoque_oxigenio": oxigenio, "estoque_agua": agua},
        telemetria=telemetria_mock,
    )


@given(parsers.parse("a tripulação é composta por {astronautas:d} astronautas"))
def tripulacao(habitat, astronautas):
    habitat.num_astronautas = astronautas
    habitat.validar_estoque()


@given(parsers.parse("a reserva mínima de segurança é de {reserva:d} kg de oxigênio"))
def reserva_minima(habitat, reserva):
    habitat.reserva_minima_oxigenio = reserva


@given(parsers.parse("um vazamento reduziu o estoque de oxigênio para {kg:d} kg"))
def vazamento(habitat, kg):
    habitat.estoque_oxigenio = kg


# ----------------------------------------------------------------------------- When
@when(parsers.parse('o astronauta "{astronauta}" solicita {kg:g} kg de oxigênio extra'))
def solicitar(habitat, contexto, astronauta, kg):
    try:
        contexto["resultado"] = habitat.solicitar_cota_extra_oxigenio(astronauta, kg)
    except OxigenioInsuficienteError as erro:
        contexto["erro"] = erro


@when(parsers.parse("o comando da missão aplica um racionamento de {percentual:d}%"))
def racionar(habitat, percentual):
    habitat.aplicar_racionamento(percentual)


@when(parsers.parse("o nível de emergência {nivel:d} é declarado"))
def declarar_emergencia(habitat, contexto, nivel):
    try:
        contexto["resultado"] = habitat.calcular_consumo_diario(nivel_emergencia=nivel)
    except NivelEmergenciaInvalidoError as erro:
        contexto["erro"] = erro


# ----------------------------------------------------------------------------- Then
@then("a solicitação deve ser aprovada")
def aprovada(contexto):
    assert contexto["erro"] is None
    assert contexto["resultado"] is not None


@then("a solicitação deve ser negada por oxigênio insuficiente")
def negada(contexto):
    assert isinstance(contexto["erro"], OxigenioInsuficienteError)


@then(parsers.parse("o estoque de oxigênio deve ser de {kg:g} kg"))
def estoque(habitat, kg):
    assert habitat.estoque_oxigenio == pytest.approx(kg)


@then("um relatório de status deve ser enviado para a Terra")
def relatorio_enviado(telemetria_mock, habitat):
    telemetria_mock.enviar_relatorio_status.assert_called_once_with(habitat.gerar_relatorio_status())


@then("nenhum alerta de crise deve ser disparado")
def sem_alerta(telemetria_mock):
    telemetria_mock.disparar_alerta_crise.assert_not_called()


@then(parsers.parse('um alerta de crise "{codigo}" deve ser disparado para a Terra'))
def alerta_disparado(telemetria_mock, codigo):
    telemetria_mock.disparar_alerta_crise.assert_called_once()
    assert telemetria_mock.disparar_alerta_crise.call_args.args[0] == codigo


@then(parsers.parse("o consumo diário de oxigênio da tripulação deve ser de {consumo:g} kg"))
def consumo_oxigenio(habitat, contexto, consumo):
    calculado = contexto["resultado"] or habitat.calcular_consumo_diario()
    assert calculado["oxigenio"] == pytest.approx(consumo)


@then("o sistema deve rejeitar o nível de emergência como inválido")
def nivel_rejeitado(contexto):
    assert isinstance(contexto["erro"], NivelEmergenciaInvalidoError)
