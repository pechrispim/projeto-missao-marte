"""Regras de negócio do controle de recursos (oxigênio e água) do Habitat de Marte."""

from src.servico_telemetria import ServicoTelemetriaEspacial, TelemetriaIndisponivelError

# Multiplicador de consumo por nível de emergência (1 = operação normal).
TAXAS_EMERGENCIA = {1: 1.0, 2: 1.25, 3: 1.5, 4: 2.0, 5: 3.0}
RACIONAMENTO_MAXIMO_PERCENTUAL = 50


class ErroRecursosMarte(Exception):
    """Classe base das exceções do ECLSS."""


class RecursoInvalidoError(ErroRecursosMarte, ValueError):
    """Valor de estoque, consumo ou quantidade inválido."""


class OxigenioInsuficienteError(ErroRecursosMarte):
    """Não há oxigênio disponível acima da reserva mínima de segurança."""


class NivelEmergenciaInvalidoError(ErroRecursosMarte, ValueError):
    """Nível de emergência fora da escala 1-5."""


class CotaRacionamentoInvalidaError(ErroRecursosMarte, ValueError):
    """Percentual de racionamento fora do intervalo permitido."""


class GerenciadorRecursosMarte:
    def __init__(
        self,
        estoque_oxigenio: float,
        estoque_agua: float,
        num_astronautas: int,
        consumo_oxigenio_por_astronauta: float = 0.84,
        consumo_agua_por_astronauta: float = 3.5,
        reserva_minima_oxigenio: float = 100.0,
        dias_alerta_autonomia: float = 30.0,
        telemetria: ServicoTelemetriaEspacial | None = None,
    ):
        self.estoque_oxigenio = estoque_oxigenio
        self.estoque_agua = estoque_agua
        self.num_astronautas = num_astronautas
        self.consumo_oxigenio_por_astronauta = consumo_oxigenio_por_astronauta
        self.consumo_agua_por_astronauta = consumo_agua_por_astronauta
        self.reserva_minima_oxigenio = reserva_minima_oxigenio
        self.dias_alerta_autonomia = dias_alerta_autonomia
        self.telemetria = telemetria if telemetria is not None else ServicoTelemetriaEspacial()
        self.fator_racionamento = 1.0
        self.historico_solicitacoes: list[dict] = []
        self.falhas_comunicacao: list[str] = []
        self.validar_estoque()

    # ------------------------------------------------------------------ validação
    def validar_estoque(self) -> None:
        for nome in ("estoque_oxigenio", "estoque_agua", "reserva_minima_oxigenio"):
            valor = getattr(self, nome)
            if not isinstance(valor, (int, float)) or isinstance(valor, bool) or valor < 0:
                raise RecursoInvalidoError(f"{nome} inválido: {valor!r}")
        for nome in ("consumo_oxigenio_por_astronauta", "consumo_agua_por_astronauta"):
            valor = getattr(self, nome)
            if not isinstance(valor, (int, float)) or isinstance(valor, bool) or valor <= 0:
                raise RecursoInvalidoError(f"{nome} deve ser positivo: {valor!r}")
        self._validar_astronautas(self.num_astronautas)

    @staticmethod
    def _validar_astronautas(num_astronautas) -> None:
        if not isinstance(num_astronautas, int) or isinstance(num_astronautas, bool) or num_astronautas <= 0:
            raise RecursoInvalidoError(f"num_astronautas inválido: {num_astronautas!r}")

    # ------------------------------------------------------------------ cálculos
    def calcular_taxa_emergencia(self, nivel: int) -> float:
        if isinstance(nivel, bool) or nivel not in TAXAS_EMERGENCIA:
            raise NivelEmergenciaInvalidoError(
                f"Nível de emergência {nivel!r} inválido (esperado 1 a 5)"
            )
        return TAXAS_EMERGENCIA[nivel]

    def calcular_consumo_diario(self, num_astronautas: int | None = None, nivel_emergencia: int = 1) -> dict:
        """Consumo total da tripulação por dia (kg de O2 e litros de água)."""
        astronautas = self.num_astronautas if num_astronautas is None else num_astronautas
        self._validar_astronautas(astronautas)
        taxa = self.calcular_taxa_emergencia(nivel_emergencia)
        fator = taxa * self.fator_racionamento
        return {
            "oxigenio": round(astronautas * self.consumo_oxigenio_por_astronauta * fator, 2),
            "agua": round(astronautas * self.consumo_agua_por_astronauta * fator, 2),
        }

    def calcular_dias_autonomia(self, nivel_emergencia: int = 1) -> float:
        """Dias até o recurso mais escasso acabar."""
        consumo = self.calcular_consumo_diario(nivel_emergencia=nivel_emergencia)
        return round(
            min(self.estoque_oxigenio / consumo["oxigenio"], self.estoque_agua / consumo["agua"]),
            1,
        )

    def oxigenio_disponivel(self) -> float:
        return max(self.estoque_oxigenio - self.reserva_minima_oxigenio, 0.0)

    # ------------------------------------------------------------------ operações
    def aplicar_racionamento(self, percentual: float) -> dict:
        """Reduz o consumo por astronauta em `percentual`% (0 < p <= 50)."""
        if (
            isinstance(percentual, bool)
            or not isinstance(percentual, (int, float))
            or not 0 < percentual <= RACIONAMENTO_MAXIMO_PERCENTUAL
        ):
            raise CotaRacionamentoInvalidaError(
                f"Racionamento de {percentual!r}% fora do intervalo (0, {RACIONAMENTO_MAXIMO_PERCENTUAL}]"
            )
        self.fator_racionamento = 1 - percentual / 100
        self._notificar_status()
        return self.calcular_consumo_diario()

    def solicitar_cota_extra_oxigenio(self, astronauta: str, quantidade: float) -> float:
        """Libera uma cota extra de O2 para um astronauta. Retorna o novo estoque."""
        if not astronauta or not str(astronauta).strip():
            raise RecursoInvalidoError("Identificação do astronauta é obrigatória")
        if isinstance(quantidade, bool) or not isinstance(quantidade, (int, float)) or quantidade <= 0:
            raise RecursoInvalidoError(f"Quantidade solicitada inválida: {quantidade!r}")

        if quantidade > self.oxigenio_disponivel():
            mensagem = (
                f"Solicitação de {quantidade} kg de O2 por {astronauta} negada: "
                f"apenas {self.oxigenio_disponivel()} kg disponíveis acima da reserva"
            )
            self._alertar("OXIGENIO_INSUFICIENTE", mensagem)
            raise OxigenioInsuficienteError(mensagem)

        self.estoque_oxigenio = round(self.estoque_oxigenio - quantidade, 2)
        self.historico_solicitacoes.append({"astronauta": astronauta, "quantidade": quantidade})
        self._notificar_status()

        autonomia = self.calcular_dias_autonomia()
        if autonomia < self.dias_alerta_autonomia:
            self._alertar(
                "AUTONOMIA_CRITICA",
                f"Autonomia do habitat reduzida para {autonomia} dias",
            )
        return self.estoque_oxigenio

    def gerar_relatorio_status(self) -> dict:
        return {
            "estoque_oxigenio": self.estoque_oxigenio,
            "estoque_agua": self.estoque_agua,
            "num_astronautas": self.num_astronautas,
            "fator_racionamento": self.fator_racionamento,
            "dias_autonomia": self.calcular_dias_autonomia(),
        }

    def encerrar(self) -> None:
        """Limpa o estado volátil do gerenciador (usado no teardown)."""
        self.historico_solicitacoes.clear()
        self.falhas_comunicacao.clear()
        self.fator_racionamento = 1.0

    # ------------------------------------------------------------------ telemetria
    def _notificar_status(self) -> None:
        try:
            self.telemetria.enviar_relatorio_status(self.gerar_relatorio_status())
        except TelemetriaIndisponivelError as erro:
            # A falha de comunicação não pode derrubar o suporte à vida.
            self.falhas_comunicacao.append(str(erro))

    def _alertar(self, codigo: str, mensagem: str) -> None:
        try:
            self.telemetria.disparar_alerta_crise(codigo, mensagem)
        except TelemetriaIndisponivelError as erro:
            self.falhas_comunicacao.append(str(erro))
