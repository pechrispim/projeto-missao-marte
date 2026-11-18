Feature: Solicitação de suprimentos de suporte à vida no Habitat de Marte
  Como astronauta do Habitat de Marte
  Quero solicitar cotas extras de oxigênio ao ECLSS
  Para executar atividades extraordinárias sem comprometer a segurança da tripulação

  Background:
    Given o habitat possui 500 kg de oxigênio e 2000 litros de água
    And a tripulação é composta por 6 astronautas
    And a reserva mínima de segurança é de 100 kg de oxigênio

  Scenario: Solicitação aprovada em condições normais
    When o astronauta "Silva" solicita 20 kg de oxigênio extra
    Then a solicitação deve ser aprovada
    And o estoque de oxigênio deve ser de 480 kg
    And um relatório de status deve ser enviado para a Terra
    And nenhum alerta de crise deve ser disparado

  Scenario: Solicitação aprovada que reduz a autonomia do habitat
    When o astronauta "Souza" solicita 380 kg de oxigênio extra
    Then a solicitação deve ser aprovada
    And o estoque de oxigênio deve ser de 120 kg
    And um alerta de crise "AUTONOMIA_CRITICA" deve ser disparado para a Terra

  Scenario: Solicitação negada em situação de crise
    Given um vazamento reduziu o estoque de oxigênio para 110 kg
    When o astronauta "Costa" solicita 50 kg de oxigênio extra
    Then a solicitação deve ser negada por oxigênio insuficiente
    And o estoque de oxigênio deve ser de 110 kg
    And um alerta de crise "OXIGENIO_INSUFICIENTE" deve ser disparado para a Terra

  Scenario: Racionamento aplicado durante a crise
    Given um vazamento reduziu o estoque de oxigênio para 110 kg
    When o comando da missão aplica um racionamento de 30%
    Then o consumo diário de oxigênio da tripulação deve ser de 3.53 kg
    And um relatório de status deve ser enviado para a Terra

  Scenario Outline: Consumo de oxigênio por nível de emergência
    When o nível de emergência <nivel> é declarado
    Then o consumo diário de oxigênio da tripulação deve ser de <consumo> kg

    Examples:
      | nivel | consumo |
      | 1     | 5.04    |
      | 3     | 7.56    |
      | 5     | 15.12   |

  Scenario: Nível de emergência inexistente é rejeitado
    When o nível de emergência 9 é declarado
    Then o sistema deve rejeitar o nível de emergência como inválido
