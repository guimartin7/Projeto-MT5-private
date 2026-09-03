# Roadmap técnico

## Etapas para operação controlada na conta Demo

1. Confirmar custos, margem e regras de execução da Clear.
2. Criar adaptador de execução isolado e exclusivo para a conta Demo.
3. Implementar pré-validação com `order_check`.
4. Garantir stop de proteção registrado no servidor.
5. Reconciliar ordens, negócios e posições com o estado da corretora.
6. Testar rejeições, desconexões, duplicidades e recuperação após falhas.
7. Adicionar habilitação manual e chave local exclusiva para o modo Demo.
8. Realizar a primeira operação Demo controlada, com um contrato e supervisão.

## 9. Interface gráfica e distribuição desktop

Criar uma aplicação desktop para Windows, permitindo operar e acompanhar a
ferramenta sem depender do terminal ou de comandos manuais. A primeira opção
técnica será PySide6/Qt; o núcleo de estratégia, risco e execução continuará
independente da interface.

### Painel

- servidor, conta e modo atual com destaque visual;
- saúde do MT5, feed e horário do último tick;
- ativo e contrato selecionado, incluindo vencimento;
- saldo, patrimônio, margem e posição reconciliada;
- resultado diário, drawdown e limites restantes;
- estratégia ativa, último sinal e justificativa da decisão;
- tabela de ordens, negócios, rejeições e alertas;
- gráfico de patrimônio e desempenho.

### Configuração segura

- capital de referência;
- quantidade máxima, inicialmente limitada a um contrato;
- stop por operação e perda diária máxima;
- máximo de entradas e janela de negociação;
- custo e slippage usados na simulação;
- seleção explícita entre histórico, paper e Demo;
- valores validados antes de serem salvos;
- nenhuma senha armazenada pela interface.

### Controles

- iniciar e parar monitoramento;
- pausar novas entradas sem impedir saídas de proteção;
- kill switch sempre visível;
- confirmação reforçada antes de habilitar o modo Demo;
- impossibilidade de habilitar conta real nesta fase;
- fechamento controlado de posição Demo;
- exportação de logs e relatório da sessão.

### Arquitetura

```text
Interface desktop
      ↓ comandos validados / eventos
Serviço da aplicação
      ↓
Dados · Estratégia · Risco · Execução · Reconciliação
      ↓
MetaTrader 5 / Clear Demo
```

A interface nunca chamará `order_send` diretamente. Toda intenção passará pelo
serviço, pelo motor de risco, pela pré-validação e pela reconciliação. O estado
exibido deverá vir da corretora, e não apenas da memória visual da aplicação.

### Distribuição

- execução pelo ícone, sem janela de terminal;
- configuração e logs em diretórios próprios do usuário;
- empacotamento opcional em `.exe` com PyInstaller;
- versão visível e diagnóstico exportável;
- atualização inicialmente manual e assinada/verificada quando o produto amadurecer.

### Critério para iniciar esta etapa

A interface será implementada depois que o adaptador Demo, os bloqueios, os
stops e a reconciliação estiverem cobertos por testes. Antes disso, poderemos
produzir apenas um protótipo visual desacoplado, sem capacidade de enviar ordens.
