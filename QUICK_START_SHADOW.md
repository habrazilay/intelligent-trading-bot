# Quick Start - Shadow Trading com Config Staging

Este guia rápido mostra como rodar o bot em modo shadow usando as configurações de staging.

## ✅ Você Já Tem Tudo!

O branch `beautiful-gagarin` já contém todas as configurações de staging. Não precisa fazer merge.

## Arquivos de Config Disponíveis

- `configs/btcusdt_1m_staging_v2.jsonc` - BTC 1 minuto (shadow trading configurado)
- `configs/btcusdt_5m_staging_v2.jsonc` - BTC 5 minutos (shadow trading configurado)

## Passo a Passo Rápido

### 1. Configure suas credenciais no `.env`

```bash
BINANCE_API_KEY=sua_chave_aqui
BINANCE_API_SECRET=seu_secret_aqui
TELEGRAM_BOT_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui
ENV_NAME=dev
ENABLE_LIVE_TRADING=false
```

### 2. Instale dependências (se ainda não fez)

```bash
pip install -r requirements.txt
```

### 3. Baixe dados e treine modelos

```bash
# Para configuração 1m
python -m scripts.download_binance -c configs/btcusdt_1m_staging_v2.jsonc
python -m scripts.merge_new -c configs/btcusdt_1m_staging_v2.jsonc
python -m scripts.features_new -c configs/btcusdt_1m_staging_v2.jsonc
python -m scripts.labels_new -c configs/btcusdt_1m_staging_v2.jsonc
python -m scripts.train -c configs/btcusdt_1m_staging_v2.jsonc
```

### 4. Rode em modo shadow

```bash
python -m service.server -c configs/btcusdt_1m_staging_v2.jsonc
```

## O Que Você Vai Ver

Com a config staging, você verá:

```
===> Start trade task. Timestamp 1702123456789
Balance: BTC = 0.00123456
Balance: USDT = 150.00
===> BUY SIGNAL {'side': 'BUY', 'close_price': 42000.0, ...}
New limit order params | side=BUY price=41916.00 quantity=0.00024 notional_usdt=10.00
NOT executed order spec: {'symbol': 'BTCUSDT', 'side': 'BUY', ...}
<=== End trade task.
```

A mensagem **"NOT executed order spec"** confirma que está em shadow mode!

## Diferenças entre Configs

### `btcusdt_1m_dev.jsonc` (Desenvolvimento)
- Usa `trader_simulation` (simulação básica)
- Não consulta balances reais
- Salva transações em arquivo local

### `btcusdt_1m_staging_v2.jsonc` (Staging - Shadow Real)
- Usa `trader_binance` com `simulate_order_execution: true`
- Consulta balances reais da Binance
- Calcula quantidades baseadas no saldo real
- **NÃO** executa ordens (shadow mode)
- Mais realista para testes antes de produção

## Configuração Shadow Trading no Staging

Veja no arquivo `configs/btcusdt_1m_staging_v2.jsonc` (linhas 176-190):

```jsonc
"trade_model": {
  "trader_binance": true,
  "no_trades_only_data_processing": false,
  "test_order_before_submit": true,
  "simulate_order_execution": false,  // ⚠️ FALSE = vai executar ordens reais!

  "percentage_used_for_trade": 2.0,
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

## ⚠️ IMPORTANTE - Config Atual Está em Modo REAL!

A config `btcusdt_1m_staging_v2.jsonc` está com:
```jsonc
"simulate_order_execution": false  // ← MODO REAL
```

### Para Ativar Shadow Mode

Você precisa mudar para:
```jsonc
"simulate_order_execution": true  // ← SHADOW MODE
```

### Dupla Segurança

Além disso, **sempre** use no `.env`:
```bash
ENABLE_LIVE_TRADING=false
```

## Editar Config para Shadow Mode

Edite `configs/btcusdt_1m_staging_v2.jsonc` linha 181:

**ANTES:**
```jsonc
"simulate_order_execution": false,
```

**DEPOIS:**
```jsonc
"simulate_order_execution": true,  // ← SHADOW MODE ATIVADO
```

Salve e rode novamente:
```bash
python -m service.server -c configs/btcusdt_1m_staging_v2.jsonc
```

## Verificação Rápida

Antes de rodar, confirme:

- [ ] `.env` tem `ENABLE_LIVE_TRADING=false`
- [ ] Config tem `"simulate_order_execution": true`
- [ ] API keys configuradas (permissão de leitura OK)
- [ ] Modelos treinados (pasta `DATA_ITB_1m/MODELS/`)

## Próximos Passos

1. ✅ Rode shadow mode por 7 dias
2. 📊 Monitore resultados e erros
3. 📈 Se tudo OK, ajuste para modo real (com MUITO cuidado!)

Para mais detalhes, veja `SHADOW_TRADING_GUIDE.md`.
