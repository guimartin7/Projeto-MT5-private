# MT5 Lab — primeira etapa

Roadmap completo: [`docs/ROADMAP.md`](docs/ROADMAP.md).

Python 3.13, ambiente virtual local e diagnostico somente leitura de conta demo.
Nao ha estrategia, backtester ou executor de ordens nesta etapa.
Nao altere permissoes de negociacao automatica para rodar este diagnostico.
A biblioteca instalada tem capacidade de negociacao, mas este projeto nao a utiliza.

## Executar no PowerShell

```powershell
cd D:\Projeto-MT5
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe diagnose.py
# Opcional: um ativo ja visivel no terminal
.\.venv\Scripts\python.exe diagnose.py --symbol EURUSD
```

Mantenha o MT5 aberto e conectado a uma conta demo. O diagnostico usa a sessao
existente; nao pede nem grava senha ou numero da conta. Consulta os ativos,
le 100 candles M1 fechados e valida ordem temporal, precos e limites OHLC.
O relatorio JSON em reports/ informa idade do tick: sucesso nao garante cotacao
recente, mercado aberto, disponibilidade de B3 ou viabilidade de uma estrategia.
Se o historico ainda nao estiver carregado, abra o grafico M1 e repita.

## Reinstalar dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Proximas etapas: escolher mercado/ativo; coletor persistente; backtest com custos;
simulacao local e motor de risco. Nenhuma operacao real esta implementada.

## Primeiro backtest (somente historico)

```powershell
.\.venv\Scripts\python.exe backtest.py
```

Por padrao, baixa 5.000 candles M5 fechados de EURUSD e testa um cruzamento
didatico de medias 20/50, com 2 pontos-base de custo em cada lado e o spread
historico do candle. O sinal no fechamento so executa na abertura seguinte.
Separa 70% do historico para desenvolvimento e 30% para teste fora da amostra,
comparando com comprar-e-manter e nao operar. Salva os
candles em CSV e as metricas/trades em JSON dentro de `reports/`. O resultado
nao e previsao nem recomendacao: e apenas a linha de base da infraestrutura.

O relatorio inclui auditoria de intervalos e uma estimativa do deslocamento do
relogio do servidor. Lacunas nao sao preenchidas: podem representar fechamento
normal do mercado e exigirao um calendario especifico quando o ativo for definido.

## Avaliacao comparativa protegida

```powershell
.\.venv\Scripts\python.exe evaluate.py
```

Compara tres estrategias fixas (tendencia por medias, rompimento/momentum e
reversao a media por RSI) em 60% de desenvolvimento e 20% de validacao.
Seleciona pelo retorno liquido da validacao e somente entao mede a escolhida nos
20% finais (holdout). O relatorio inclui fator de lucro, medias de ganhos/perdas,
sequencia maxima de perdas e exposicao. Depois de exibido, esse holdout nao deve
ser usado para ajustar os parametros; uma proxima avaliacao honesta exige dados
mais recentes ainda nao vistos.

## Paper trading local

Uma leitura segura, sem ordens:

```powershell
.\.venv\Scripts\python.exe paper_trade.py
```

Monitor continuo (encerre com Ctrl+C):

```powershell
.\.venv\Scripts\python.exe paper_trade.py --watch --interval 30
```

O saldo, a posicao e os negocios ficticios ficam em `paper/`. O programa recusa
contas reais, processa cada candle fechado uma unica vez e nao chama `order_send`.
A estrategia SMA usada aqui foi reprovada no backtest (`strategy_approved=false`):
este modo existe apenas para testar estabilidade, persistencia e fluxo operacional.

Limites padrao: perda diaria de 1%, drawdown de 2% e cinco entradas por dia.
Para bloquear novas entradas imediatamente, crie o arquivo vazio
`paper/KILL_SWITCH`. Saidas continuam permitidas. Cada decisao e registrada em
`paper/EURUSD-M5-events.jsonl` para auditoria.

O simulador valida a idade da cotacao compensando o deslocamento estimado do
servidor e bloqueia decisões com feed ausente, antigo ou invalido. Entradas e
saidas ficticias usam o Bid/Ask atual; o candle fechado serve apenas para o sinal.
Para consultar o estado sem conectar ao MT5:

```powershell
.\.venv\Scripts\python.exe paper_status.py
```

Exemplo configuravel:

```powershell
.\.venv\Scripts\python.exe backtest.py --symbol EURUSD --timeframe M15 --bars 10000 --fast 20 --slow 50 --cost-bps 3
```

Referencia: https://www.mql5.com/en/docs/python_metatrader5

## Treinamento B3 / Clear

Com o terminal conectado ao servidor `ClearInvestimentos-DEMO`:

```powershell
.\.venv\Scripts\python.exe b3_backtest.py
```

O perfil inicial usa `WINV26`, M5, saldo local de R$ 500 e exatamente um
minicontrato. Considera R$ 0,20 por ponto, tick de 5 pontos, um tick de slippage,
stop de R$ 20, limite diário de R$ 30 e zeragem intradiária. O custo padrão de
R$ 1 por lado é apenas uma hipótese conservadora até confirmarmos todas as tarifas.
Este módulo não contém chamada de envio de ordens e nunca altera a conta demo.
O histórico é dividido cronologicamente em 70% para desenvolvimento e 30% para
teste fora da amostra. Se o saldo ficar abaixo do risco mínimo de uma operação,
novas entradas são bloqueadas.

Paper trading específico da B3:

```powershell
.\.venv\Scripts\python.exe b3_paper.py
.\.venv\Scripts\python.exe b3_paper.py --watch --interval 30
```

O estado separado fica em `paper/WINV26-M5-state.json`. Fora do pregão, o
programa apenas aguarda. O arquivo vazio `paper/B3_KILL_SWITCH` bloqueia entradas
e encerra posições fictícias na próxima cotação saudável. Nenhuma função de
envio, alteração ou cancelamento de ordens existe neste módulo.

Pré-validação da futura ordem Demo (somente durante a janela de entrada):

```powershell
.\.venv\Scripts\python.exe demo_preflight.py --direction buy
```

Esse comando exige Clear Demo, Netting, `WINV26`, um contrato, nenhuma exposição
prévia, feed saudável e negociação algorítmica habilitada. Calcula margem e chama
apenas `order_check`; nunca chama `order_send`.
