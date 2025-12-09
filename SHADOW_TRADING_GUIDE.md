# Guia de Shadow Trading

Este guia explica como configurar e testar o modo shadow (simulação) do bot antes de fazer trades reais.

## O que é Shadow Trading?

Shadow trading permite que o bot execute toda a lógica de trading (análise, sinais, decisões) **sem executar ordens reais** na exchange. É essencial para testar estratégias antes de arriscar dinheiro real.

## 3 Modos de Operação

### 1. Simulação Básica (`trader_simulation`)

**Onde:** `outputs/notifier_trades.py`

**O que faz:**
- Rastreia sinais de BUY/SELL
- Salva transações simuladas em arquivo local
- Calcula lucro/prejuízo teórico
- Envia notificações ao Telegram
- **NÃO** interage com a Binance

**Configuração:**
```jsonc
"output_sets": [
  {
    "generator":"trader_simulation",
    "config":{
      "buy_signal_column":"buy_signal",
      "sell_signal_column":"sell_signal"
    }
  }
]
```

**Prós:**
- Simples e rápido
- Não precisa de saldo real
- Não precisa de permissões de trade na API

**Contras:**
- Não testa a lógica real de orders/balances
- Não considera slippage, fees, ou rejeições de ordem

---

### 2. Shadow Trading Completo (`trader_binance` + `simulate_order_execution`)

**Onde:** `outputs/trader_binance.py`

**O que faz:**
- Executa **TODA** a lógica real de trading
- Consulta balances reais da Binance
- Calcula quantidades baseadas no saldo
- Valida parâmetros de ordem
- **NÃO** envia ordens para a Binance (linha 490-492)
- Apenas imprime o que seria executado

**Configuração:**
```jsonc
"trade_model": {
  "trader_binance": true,
  "simulate_order_execution": true,  // ← SHADOW MODE
  "test_order_before_submit": false,
  "no_trades_only_data_processing": false,

  "percentage_used_for_trade": 2.0,
  "min_notional_usdt": 5.0,
  "min_balance_usdt_for_percentage": 500.0,
  "limit_price_adjustment": 0.002
},

"base_asset": "BTC",
"quote_asset": "USDT",

"output_sets": [
  {
    "generator":"trader_binance",
    "config":{
      "buy_signal_column":"buy_signal",
      "sell_signal_column":"sell_signal"
    }
  }
]
```

**Variável de ambiente importante:**
```bash
ENABLE_LIVE_TRADING=false  # Dupla segurança
```

**Prós:**
- Testa toda a lógica de trading
- Usa balances reais para calcular quantidades
- Valida limites e filtros da Binance
- Detecta problemas antes de trades reais

**Contras:**
- Precisa de API keys com permissão de leitura
- Precisa ter algum saldo na conta

---

### 3. Trading Real (`trader_binance` sem simulate)

**⚠️ CUIDADO! Executa ordens reais!**

**Configuração:**
```jsonc
"trade_model": {
  "trader_binance": true,
  "simulate_order_execution": false,  // ← MODO REAL
  "test_order_before_submit": true,   // Recomendado: testa antes
  "no_trades_only_data_processing": false,

  "percentage_used_for_trade": 2.0,  // Comece com valores PEQUENOS!
  "min_notional_usdt": 5.0,
  "min_balance_usdt_for_percentage": 500.0,
  "limit_price_adjustment": 0.002
},

"output_sets": [
  {
    "generator":"trader_binance",
    "config":{
      "buy_signal_column":"buy_signal",
      "sell_signal_column":"sell_signal"
    }
  }
]
```

**Variável de ambiente:**
```bash
ENABLE_LIVE_TRADING=true
```

---

## Como Testar Shadow Trading

### Passo 1: Configure API Keys (Somente Leitura)

No arquivo `.env`:
```bash
BINANCE_API_KEY=sua_chave_aqui
BINANCE_API_SECRET=seu_secret_aqui
TELEGRAM_BOT_TOKEN=seu_token_aqui  # opcional
TELEGRAM_CHAT_ID=seu_chat_id_aqui  # opcional
ENV_NAME=dev
ENABLE_LIVE_TRADING=false  # IMPORTANTE!
```

### Passo 2: Use Config de Shadow Trading

Crie ou edite um config (ex: `configs/btcusdt_1m_shadow.jsonc`):

```jsonc
{
  "train": false,
  "venue": "binance",

  "api_key": "",  // Lê do .env
  "api_secret": "",

  "symbol": "BTCUSDT",
  "freq": "1m",
  "pandas_freq": "1min",
  "data_folder": "./DATA_ITB_1m_shadow",

  // ... suas features, labels, algorithms ...

  "trade_model": {
    "trader_binance": true,
    "simulate_order_execution": true,  // ← SHADOW
    "test_order_before_submit": false,
    "percentage_used_for_trade": 2.0,
    "min_notional_usdt": 5.0,
    "min_balance_usdt_for_percentage": 500.0,
    "limit_price_adjustment": 0.002
  },

  "base_asset": "BTC",
  "quote_asset": "USDT",

  "output_sets": [
    {
      "generator":"trader_binance",
      "config":{
        "buy_signal_column":"buy_signal",
        "sell_signal_column":"sell_signal"
      }
    }
  ]
}
```

### Passo 3: Treine os Modelos

```bash
python -m scripts.download_binance -c configs/btcusdt_1m_shadow.jsonc
python -m scripts.merge_new -c configs/btcusdt_1m_shadow.jsonc
python -m scripts.features_new -c configs/btcusdt_1m_shadow.jsonc
python -m scripts.labels_new -c configs/btcusdt_1m_shadow.jsonc
python -m scripts.train -c configs/btcusdt_1m_shadow.jsonc
```

### Passo 4: Rode o Servidor em Shadow Mode

```bash
python -m service.server -c configs/btcusdt_1m_shadow.jsonc
```

**O que você verá:**
```
===> Start trade task. Timestamp 1234567890
===> BUY SIGNAL {'side': 'BUY', 'close_price': 42000.0, ...}
New limit order params | side=BUY price=41916.00 quantity=0.00024 notional_usdt=10.00
NOT executed order spec: {'symbol': 'BTCUSDT', 'side': 'BUY', ...}
<=== End trade task.
```

**Nota:** A mensagem `NOT executed order spec` confirma que está em shadow mode!

---

## Verificação de Segurança

Antes de ir para trading real, verifique:

### ✅ Checklist de Shadow Trading

- [ ] `ENABLE_LIVE_TRADING=false` no .env
- [ ] `simulate_order_execution: true` no trade_model
- [ ] Bot roda sem erros por pelo menos 24h
- [ ] Sinais de BUY/SELL são gerados corretamente
- [ ] Quantidades calculadas estão corretas
- [ ] Preços limit estão dentro dos filtros Binance
- [ ] Logs mostram "NOT executed order spec"
- [ ] Nenhuma ordem aparece na Binance (verificar manualmente)

### ✅ Checklist para Trading Real

- [ ] Shadow trading testado por **mínimo 1 semana**
- [ ] Resultados do shadow são lucrativos
- [ ] API keys com permissão de SPOT trading
- [ ] `percentage_used_for_trade` configurado com valor PEQUENO (1-5%)
- [ ] `min_notional_usdt` acima do mínimo Binance (≥5 USDT)
- [ ] `test_order_before_submit: true` ativado
- [ ] Comece com par de baixo valor (ex: pequenas quantidades)
- [ ] Monitore **constantemente** nas primeiras horas

---

## Arquivos de Log/Dados

### Shadow Trading (trader_simulation)
- Transações salvas em: `DATA_ITB_1m/BTCUSDT/transactions.txt`
- Formato: `timestamp,price,profit,status`

### Shadow Trading (trader_binance simulate)
- Apenas logs no console
- Nenhum arquivo de transação
- Use os logs do service para análise

### Trading Real
- Ordens reais na Binance
- Logs em console + arquivos
- Verifique na interface Binance também

---

## Troubleshooting

### Erro: "BINANCE_API_KEY não encontrado"
- Verifique se `.env` existe e está configurado
- Verifique se está na pasta correta ao rodar o comando

### Erro: "Invalid API key"
- Confirme que as keys estão corretas
- Verifique se tem permissão de leitura

### Erro: "MIN_NOTIONAL filter"
- Aumente `min_notional_usdt` para ≥ 5.0
- Ou aumente `percentage_used_for_trade`

### Não vejo "NOT executed order spec"
- Verifique `simulate_order_execution: true`
- Verifique se está usando `trader_binance` (não `trader_simulation`)

### Sinais não são gerados
- Verifique os thresholds em `signal_sets`
- Veja o valor de `trade_score` nos logs
- Pode estar fora da zona de threshold

---

## Comparação dos Modos

| Característica | trader_simulation | trader_binance (shadow) | trader_binance (real) |
|---|---|---|---|
| Consulta Binance | ❌ Não | ✅ Sim (read-only) | ✅ Sim |
| Usa balance real | ❌ Não | ✅ Sim | ✅ Sim |
| Executa ordens | ❌ Não | ❌ Não | ✅ SIM |
| Calcula quantities | ⚠️ Simplificado | ✅ Real | ✅ Real |
| Valida limites | ❌ Não | ✅ Sim | ✅ Sim |
| Grava transações | ✅ Sim | ❌ Não | ✅ Sim |
| Precisa de saldo | ❌ Não | ⚠️ Mínimo | ✅ Sim |
| Recomendado para | Teste inicial | Teste avançado | Produção |

---

## Exemplo de Config Completo

Veja `configs/btcusdt_1m_staging_v2.jsonc` para um exemplo completo de configuração de shadow trading.

---

## Próximos Passos

1. ✅ Rode `trader_simulation` por 3-7 dias
2. ✅ Rode `trader_binance` shadow por 7-14 dias
3. ⚠️ Ative trading real com valores MÍNIMOS
4. 📊 Monitore constantemente
5. 📈 Aumente gradualmente os valores após confiança

**Nunca pule etapas! Shadow trading economiza muito dinheiro em erros.**
