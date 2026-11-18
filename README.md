[![CI - Missão Marte ECLSS](https://github.com/pechrispim/projeto-missao-marte/actions/workflows/pipeline.yml/badge.svg)](https://github.com/pechrispim/projeto-missao-marte/actions/workflows/pipeline.yml)

# Missão Marte — Testes Automatizados do ECLSS

Suíte de testes automatizados do **Environmental Control and Life Support System (ECLSS)** do Habitat de Marte, cobrindo testes unitários e de integração com **pytest**, isolamento com **pytest-mock**, automação Web E2E com **Selenium WebDriver (headless)**, cenários **BDD** com **pytest-bdd** e integração contínua no **GitHub Actions** com relatório de cobertura (**pytest-cov**).

## Sistema sob teste

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| `GerenciadorRecursosMarte` | `src/gerenciador_recursos.py` | Valida estoques de O₂ e água, calcula consumo por astronauta/dia, taxa de emergência (níveis 1–5), autonomia e racionamento; libera cotas extras de O₂ respeitando a reserva mínima. |
| `ServicoTelemetriaEspacial` | `src/servico_telemetria.py` | Dependência externa (HTTP) que envia relatórios de status e alertas de crise à Terra. |
| `PainelControleWeb` | `web/painel.html` | Painel para consultar os níveis e solicitar cota extra de O₂ (com latência assíncrona simulada). |

Exceções customizadas: `RecursoInvalidoError`, `OxigenioInsuficienteError`, `NivelEmergenciaInvalidoError`, `CotaRacionamentoInvalidaError`.

## Estrutura

```
projeto-missao-marte/
├── .github/workflows/pipeline.yml   # CI: checkout, setup-python, deps, pytest + cobertura
├── src/
│   ├── gerenciador_recursos.py
│   └── servico_telemetria.py
├── tests/
│   ├── conftest.py                  # fixtures (sessão, function + yield, WebDriver, mocks, screenshot)
│   ├── dados/parametros_habitat.json
│   ├── test_gerenciador.py          # Req. 1 e 2: parametrização, exceções, mocks
│   ├── test_servico_telemetria.py   # serviço de telemetria com urlopen mockado
│   ├── test_selenium_e2e.py         # Req. 3: E2E headless com esperas explícitas
│   ├── test_bdd.py                  # Req. 4: steps @given/@when/@then
│   └── features/solicitacao_oxigenio.feature
├── web/painel.html
├── pytest.ini
└── requirements.txt
```

## Como os requisitos foram atendidos

**1. Pytest — fixtures, parametrização e exceções**
- `parametros_habitat` (escopo `session`, em `conftest.py`) carrega os parâmetros iniciais de `tests/dados/parametros_habitat.json` e, no teardown, verifica que nenhum teste os alterou.
- `gerenciador` (escopo `function`) entrega uma instância limpa por teste usando `yield` para setup/teardown (`encerrar()`).
- `@pytest.mark.parametrize` cobre consumo diário × nº de astronautas × nível de emergência, taxas de emergência, autonomia, racionamento e solicitações.
- `pytest.raises(...)` valida `OxigenioInsuficienteError`, `NivelEmergenciaInvalidoError`, `RecursoInvalidoError` e `CotaRacionamentoInvalidaError`.

**2. Mocks**
- `telemetria_mock` usa `mocker.create_autospec(ServicoTelemetriaEspacial)`; `mocker.patch` substitui a classe e o `urlopen`.
- `assert_called_once_with` confirma os argumentos exatos dos alertas (`OXIGENIO_INSUFICIENTE`, `AUTONOMIA_CRITICA`) e dos relatórios.
- `side_effect` simula a estação terrestre fora do ar, e o habitat continua operando.
- A fixture `autouse` `bloquear_rede` faz falhar qualquer teste que tente uma chamada HTTP real da telemetria.

**3. Selenium E2E**
- A fixture `driver` sobe o Chrome com `--headless=new` e chama `driver.quit()` no teardown.
- O fluxo de solicitação de O₂ é automatizado via Page Object. A sincronização usa só `WebDriverWait` + `expected_conditions`, sem `time.sleep()`.
- Se um teste falhar, o hook `pytest_runtest_makereport` dispara `driver.save_screenshot()` em `screenshots/`. No CI essas imagens são publicadas como artifact.

**4. BDD**
- `tests/features/solicitacao_oxigenio.feature` descreve cenários normais e de crise (Given/When/Then, Background e Scenario Outline).
- `tests/test_bdd.py` mapeia os passos com `@given`, `@when` e `@then` (`pytest-bdd`).

**5. CI**
- `.github/workflows/pipeline.yml` roda em `push` e `pull_request`, usando `actions/checkout@v4` e `actions/setup-python@v5`, e executa `pytest --cov=src --cov-report=term-missing`.

## Execução local

Pré-requisitos: Python 3.10+ e Google Chrome instalado. O Selenium Manager baixa o ChromeDriver automaticamente.

```bash
# 1. Clonar o repositório
git clone https://github.com/pechrispim/projeto-missao-marte.git
cd projeto-missao-marte

# 2. (Opcional) Criar e ativar um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Instalar os requisitos
pip install -r requirements.txt

# 4. Executar a suíte completa (o relatório de cobertura sai no console)
pytest
```

Execuções parciais:

```bash
pytest tests/test_gerenciador.py   # unitários + mocks
pytest -m e2e                      # apenas Selenium
pytest -m bdd                      # apenas cenários BDD
pytest -m "not e2e"                # tudo, exceto o navegador
```
