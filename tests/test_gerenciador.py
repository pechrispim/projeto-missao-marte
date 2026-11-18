"""Testes unitários e de integração do GerenciadorRecursosMarte.

Requisito 1: fixtures, parametrização e exceções.
Requisito 2: isolamento do ServicoTelemetriaEspacial com mocks.
"""

import pytest

from src.gerenciador_recursos import (
    CotaRacionamentoInvalidaError,
    GerenciadorRecursosMarte,
    NivelEmergenciaInvalidoError,
    OxigenioInsuficienteError,
    RecursoInvalidoError,
)
from src.servico_telemetria import TelemetriaIndisponivelError


# =========================================================================== Requisito 1
class TestInicializacaoEValidacao:
    def test_fixture_carrega_parametros_iniciais(self, gerenciador, parametros_habitat):
        assert gerenciador.estoque_oxigenio == parametros_habitat["estoque_oxigenio"]
        assert gerenciador.estoque_agua == parametros_habitat["estoque_agua"]
        assert gerenciador.num_astronautas == parametros_habitat["num_astronautas"]
        assert gerenciador.fator_racionamento == 1.0

    def test_instancias_sao_isoladas_entre_testes_parte_1(self, gerenciador):
        gerenciador.solicitar_cota_extra_oxigenio("Silva", 50)
        assert gerenciador.estoque_oxigenio == 450

    def test_instancias_sao_isoladas_entre_testes_parte_2(self, gerenciador):
        # A fixture de escopo function entrega um objeto novo: nada da "parte 1" vazou.
        assert gerenciador.estoque_oxigenio == 500
        assert gerenciador.historico_solicitacoes == []

    @pytest.mark.parametrize(
        "campo, valor",
        [
            ("estoque_oxigenio", -1),
            ("estoque_agua", -0.5),
            ("estoque_oxigenio", "500"),
            ("reserva_minima_oxigenio", -10),
            ("consumo_oxigenio_por_astronauta", 0),
            ("consumo_agua_por_astronauta", -3.5),
            ("num_astronautas", 0),
            ("num_astronautas", -2),
            ("num_astronautas", 2.5),
            ("num_astronautas", True),
        ],
    )
    def test_parametros_invalidos_levantam_erro(self, parametros_habitat, telemetria_mock, campo, valor):
        parametros = {**parametros_habitat, campo: valor}
        with pytest.raises(RecursoInvalidoError, match=campo):
            GerenciadorRecursosMarte(**parametros, telemetria=telemetria_mock)


class TestCalculoConsumo:
    @pytest.mark.parametrize(
        "num_astronautas, nivel, oxigenio_esperado, agua_esperada",
        [
            (1, 1, 0.84, 3.5),
            (4, 1, 3.36, 14.0),
            (6, 1, 5.04, 21.0),
            (6, 2, 6.3, 26.25),
            (6, 3, 7.56, 31.5),
            (6, 4, 10.08, 42.0),
            (6, 5, 15.12, 63.0),
            (10, 3, 12.6, 52.5),
        ],
        ids=lambda v: str(v),
    )
    def test_consumo_diario_por_astronautas_e_nivel(
        self, gerenciador, num_astronautas, nivel, oxigenio_esperado, agua_esperada
    ):
        consumo = gerenciador.calcular_consumo_diario(num_astronautas, nivel_emergencia=nivel)
        assert consumo["oxigenio"] == pytest.approx(oxigenio_esperado)
        assert consumo["agua"] == pytest.approx(agua_esperada)

    @pytest.mark.parametrize("nivel, taxa", [(1, 1.0), (2, 1.25), (3, 1.5), (4, 2.0), (5, 3.0)])
    def test_taxa_emergencia_valida(self, gerenciador, nivel, taxa):
        assert gerenciador.calcular_taxa_emergencia(nivel) == taxa

    @pytest.mark.parametrize("nivel_invalido", [0, 6, -1, 99, 2.5, "3", None, True])
    def test_taxa_emergencia_invalida(self, gerenciador, nivel_invalido):
        with pytest.raises(NivelEmergenciaInvalidoError, match="inválido"):
            gerenciador.calcular_taxa_emergencia(nivel_invalido)

    def test_nivel_invalido_propaga_no_calculo_de_consumo(self, gerenciador):
        with pytest.raises(NivelEmergenciaInvalidoError):
            gerenciador.calcular_consumo_diario(nivel_emergencia=7)

    @pytest.mark.parametrize("astronautas_invalido", [0, -3, 1.5])
    def test_consumo_com_tripulacao_invalida(self, gerenciador, astronautas_invalido):
        with pytest.raises(RecursoInvalidoError):
            gerenciador.calcular_consumo_diario(astronautas_invalido)

    @pytest.mark.parametrize(
        "oxigenio, agua, nivel, dias_esperados",
        [
            (500, 2000, 1, 95.2),   # água é o recurso limitante
            (100, 2000, 1, 19.8),   # oxigênio é o recurso limitante
            (500, 2000, 5, 31.7),   # emergência máxima triplica o consumo
            (0, 2000, 1, 0.0),
        ],
    )
    def test_dias_autonomia(self, gerenciador, oxigenio, agua, nivel, dias_esperados):
        gerenciador.estoque_oxigenio = oxigenio
        gerenciador.estoque_agua = agua
        assert gerenciador.calcular_dias_autonomia(nivel) == pytest.approx(dias_esperados)


class TestRacionamento:
    @pytest.mark.parametrize(
        "percentual, oxigenio_esperado, agua_esperada",
        [(10, 4.54, 18.9), (25, 3.78, 15.75), (30, 3.53, 14.7), (50, 2.52, 10.5)],
    )
    def test_aplicar_cota_de_racionamento(self, gerenciador, percentual, oxigenio_esperado, agua_esperada):
        consumo = gerenciador.aplicar_racionamento(percentual)
        assert consumo["oxigenio"] == pytest.approx(oxigenio_esperado)
        assert consumo["agua"] == pytest.approx(agua_esperada)

    def test_racionamento_aumenta_autonomia(self, gerenciador):
        antes = gerenciador.calcular_dias_autonomia()
        gerenciador.aplicar_racionamento(50)
        assert gerenciador.calcular_dias_autonomia() == pytest.approx(antes * 2, abs=0.1)

    @pytest.mark.parametrize("percentual", [0, -5, 51, 100, "20", None, True])
    def test_racionamento_fora_do_intervalo(self, gerenciador, percentual):
        with pytest.raises(CotaRacionamentoInvalidaError):
            gerenciador.aplicar_racionamento(percentual)
        assert gerenciador.fator_racionamento == 1.0


class TestSolicitacaoCotaExtra:
    @pytest.mark.parametrize("quantidade, estoque_esperado", [(0.5, 499.5), (20, 480), (150, 350), (400, 100)])
    def test_solicitacao_aprovada(self, gerenciador, quantidade, estoque_esperado):
        assert gerenciador.solicitar_cota_extra_oxigenio("Costa", quantidade) == estoque_esperado
        assert gerenciador.historico_solicitacoes == [{"astronauta": "Costa", "quantidade": quantidade}]

    @pytest.mark.parametrize("quantidade", [400.01, 450, 1000])
    def test_oxigenio_insuficiente(self, gerenciador, quantidade):
        with pytest.raises(OxigenioInsuficienteError, match="negada"):
            gerenciador.solicitar_cota_extra_oxigenio("Costa", quantidade)
        assert gerenciador.estoque_oxigenio == 500
        assert gerenciador.historico_solicitacoes == []

    def test_estoque_na_reserva_bloqueia_qualquer_solicitacao(self, gerenciador):
        gerenciador.estoque_oxigenio = 100
        with pytest.raises(OxigenioInsuficienteError):
            gerenciador.solicitar_cota_extra_oxigenio("Costa", 0.01)

    @pytest.mark.parametrize(
        "astronauta, quantidade",
        [("", 10), ("   ", 10), (None, 10), ("Costa", 0), ("Costa", -5), ("Costa", "10"), ("Costa", True)],
    )
    def test_solicitacao_invalida(self, gerenciador, telemetria_mock, astronauta, quantidade):
        with pytest.raises(RecursoInvalidoError):
            gerenciador.solicitar_cota_extra_oxigenio(astronauta, quantidade)
        telemetria_mock.enviar_relatorio_status.assert_not_called()
        telemetria_mock.disparar_alerta_crise.assert_not_called()


# =========================================================================== Requisito 2
class TestIsolamentoTelemetria:
    def test_solicitacao_normal_envia_relatorio_sem_alerta(self, gerenciador, telemetria_mock):
        gerenciador.solicitar_cota_extra_oxigenio("Costa", 20)

        telemetria_mock.enviar_relatorio_status.assert_called_once_with(
            {
                "estoque_oxigenio": 480,
                "estoque_agua": 2000.0,
                "num_astronautas": 6,
                "fator_racionamento": 1.0,
                "dias_autonomia": 95.2,
            }
        )
        telemetria_mock.disparar_alerta_crise.assert_not_called()

    def test_oxigenio_insuficiente_dispara_alerta_de_crise(self, gerenciador, telemetria_mock):
        with pytest.raises(OxigenioInsuficienteError):
            gerenciador.solicitar_cota_extra_oxigenio("Costa", 450)

        telemetria_mock.disparar_alerta_crise.assert_called_once_with(
            "OXIGENIO_INSUFICIENTE",
            "Solicitação de 450 kg de O2 por Costa negada: "
            "apenas 400.0 kg disponíveis acima da reserva",
        )
        telemetria_mock.enviar_relatorio_status.assert_not_called()

    def test_autonomia_baixa_dispara_alerta_apos_aprovacao(self, gerenciador, telemetria_mock):
        gerenciador.solicitar_cota_extra_oxigenio("Costa", 380)  # restam 120 kg -> 23.8 dias

        telemetria_mock.enviar_relatorio_status.assert_called_once()
        telemetria_mock.disparar_alerta_crise.assert_called_once_with(
            "AUTONOMIA_CRITICA", "Autonomia do habitat reduzida para 23.8 dias"
        )

    def test_racionamento_notifica_terra(self, gerenciador, telemetria_mock):
        gerenciador.aplicar_racionamento(50)
        relatorio = telemetria_mock.enviar_relatorio_status.call_args.args[0]
        assert relatorio["fator_racionamento"] == 0.5
        assert relatorio["dias_autonomia"] == pytest.approx(190.5)

    def test_falha_de_rede_nao_derruba_o_habitat(self, gerenciador, telemetria_mock):
        telemetria_mock.enviar_relatorio_status.side_effect = TelemetriaIndisponivelError("sem sinal")
        telemetria_mock.disparar_alerta_crise.side_effect = TelemetriaIndisponivelError("tempestade solar")

        assert gerenciador.solicitar_cota_extra_oxigenio("Costa", 380) == 120
        assert gerenciador.falhas_comunicacao == ["sem sinal", "tempestade solar"]

    def test_mocker_patch_substitui_servico_padrao(self, mocker, parametros_habitat):
        """Sem injeção explícita, o gerenciador cria o serviço real — aqui ele é interceptado."""
        classe_mock = mocker.patch("src.gerenciador_recursos.ServicoTelemetriaEspacial")
        estacao = classe_mock.return_value

        gerenciador = GerenciadorRecursosMarte(**parametros_habitat)
        with pytest.raises(OxigenioInsuficienteError):
            gerenciador.solicitar_cota_extra_oxigenio("Souza", 999)

        classe_mock.assert_called_once_with()
        assert gerenciador.telemetria is estacao
        estacao.disparar_alerta_crise.assert_called_once_with(
            "OXIGENIO_INSUFICIENTE",
            "Solicitação de 999 kg de O2 por Souza negada: "
            "apenas 400.0 kg disponíveis acima da reserva",
        )

    def test_mock_simula_resposta_da_estacao_terrestre(self, gerenciador, telemetria_mock):
        telemetria_mock.disparar_alerta_crise.return_value = {"protocolo": "ALERTA-4242", "eta_resgate_dias": 300}
        with pytest.raises(OxigenioInsuficienteError):
            gerenciador.solicitar_cota_extra_oxigenio("Costa", 401)
        resposta = telemetria_mock.disparar_alerta_crise.return_value
        assert resposta["protocolo"] == "ALERTA-4242"
        assert telemetria_mock.disparar_alerta_crise.call_count == 1
