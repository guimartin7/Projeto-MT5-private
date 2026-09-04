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
R$ 1 por lado separa corretagem Clear (R$ 0) de uma hipótese conservadora e
configurável para taxas B3. Liquidação compulsória não entra no custo normal.
Além disso, novas entradas são interrompidas ao atingir R$ 100 de drawdown a
partir do pico e o limite operacional é de três entradas por dia, alinhado à
política da futura execução Demo.
Este módulo não contém chamada de envio de ordens e nunca altera a conta demo.
O histórico é dividido cronologicamente em 70% para desenvolvimento e 30% para
teste fora da amostra. Se o saldo ficar abaixo do risco mínimo de uma operação,
novas entradas são bloqueadas.

O relatório também calcula fator de lucro, expectativa por operação, pior
sequência de perdas, drawdown percentual e um intervalo exploratório para a
expectativa. Um portão de pesquisa exige no teste fora da amostra pelo menos 30
operações, resultado e expectativa positivos, fator de lucro mínimo de 1,20 e
drawdown máximo de 20% nos dois períodos. O limite inferior do intervalo
exploratório de 95% da expectativa também precisa ficar acima de zero. Mesmo
`PASS_RESEARCH_GATE` nunca autoriza ordens: ele serve apenas para decidir se vale
avançar para a próxima validação.

Teste exploratório com cenários fixos de custo e slippage:

```powershell
.\.venv\Scripts\python.exe b3_stress.py
```

Os cenários baseline, adverso e severo são avaliados separadamente e não servem
para escolher parâmetros. A estratégia só é marcada como robusta se passar pelo
portão de pesquisa nos três; mesmo assim, dados futuros continuam obrigatórios.

Seleção de sinais sem executar a reserva cronológica final:

```powershell
.\.venv\Scripts\python.exe b3_candidate_selection.py
```

São comparados parâmetros fixos de SMA 9/21, SMA 20/50 e rompimentos de 20 e 40
candles. Apenas os primeiros 80% entram no cálculo; os 20% finais ficam sem
métricas de desempenho nesse relatório. Como esse período já apareceu em
análises anteriores, ele é uma reserva técnica, não um holdout cientificamente
virgem. A confirmação definitiva dependerá de candles futuros ainda não vistos.
Também há uma variante SMA 20/50 com filtro de distância mínima de 20 pontos
entre as médias, para evitar cruzamentos sem força.

Diagnóstico de margem, sem `order_check` e sem `order_send`:

```powershell
.\.venv\Scripts\python.exe margin_diagnostic.py
```

A referência pública versionada é R$ 155 por WIN no day trade, mas o cálculo
do servidor MT5, quando houver cotação válida, sempre prevalece. Fora do pregão
o diagnóstico informa indisponibilidade em vez de estimar margem como confirmada.

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

Reconciliação somente leitura da conta Demo:

```powershell
.\.venv\Scripts\python.exe reconcile_demo.py
```

O comando classifica a exposição como limpa, gerenciada ou conflitante, distingue
posições/ordens manuais pelo identificador do projeto e compara a corretora com o
estado local esperado. Divergências bloqueiam futuras entradas.

Estado das barreiras de execução, também somente leitura:

```powershell
.\.venv\Scripts\python.exe execution_readiness.py
```

O diário de execução usa um ID determinístico por ativo, candle e direção. Uma
tentativa com resultado desconhecido bloqueia qualquer nova intenção até haver
evidência da corretora ou revisão manual. Isso evita duplicação após reinício ou
queda entre o envio e a gravação da resposta.

O gateway Demo exige preparação e execução separadas. A preparação chama
`order_check`, persiste a intenção e exibe uma frase específica. A execução exige
essa frase simultaneamente no argumento e na variável `MT5_DEMO_EXECUTION_ARM`.
O estado `SENT` é gravado antes de `order_send`; após a resposta, somente uma
posição de um contrato com o identificador correto e stop confirmado recebe o
estado `CONFIRMED`. O comando de execução não deve ser usado antes da primeira
operação supervisionada e explicitamente autorizada.

Mesmo com a frase dupla, o envio permanece bloqueado sem um arquivo local
`paper/DEMO_EXECUTION_PERMIT.json`, válido somente para a data corrente e contendo
servidor, ativo e volume exatos. A política também recalcula pela própria Clear o
resultado diário e o número de entradas do projeto; os limites iniciais são perda
de R$ 30 e três entradas. O arquivo de permissão não é versionado.

Recuperação após queda ou resultado inconclusivo:

```powershell
.\.venv\Scripts\python.exe recover_demo.py
```

Esse comando nunca envia ordens. Ele usa posições, ordens e negócios da Clear
para confirmar intenções `SENT`/`UNKNOWN` e cancela preparações de dias anteriores
somente quando a corretora está completamente zerada. Evidência parcial ou posição
sem stop permanece bloqueada para revisão.
