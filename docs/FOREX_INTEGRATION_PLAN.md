# Plano de Integração Forex

## Resumo Executivo

Expandir o Intelligent Trading Bot para operar no mercado Forex além de crypto.
O Forex oferece menor volatilidade, mais previsibilidade e opera 24/5.

---

## Comparativo de Corretoras Forex com API

| Corretora | API Type | Python SDK | Taxa API | Spreads | Regulação | Recomendação |
|-----------|----------|------------|----------|---------|-----------|--------------|
| **OANDA** | REST + Streaming | Sim (v20) | Grátis | Baixos | FCA, CFTC | ⭐ **MELHOR OPÇÃO** |
| **IG Markets** | REST + Streaming | Sim | Grátis | Médios | FCA | ✅ Boa alternativa |
| **Interactive Brokers** | TWS API | Sim | Grátis | Muito baixos | SEC, FCA | ✅ Para profissionais |
| **FXCM** | REST | Sim | Grátis | Médios | FCA | ✅ Boa para iniciantes |
| **Pepperstone** | MT4/MT5 | Via MQL | Grátis | Baixos | ASIC, FCA | ⚠️ Menos flexível |
| **XTB** | xStation API | Sim | Grátis | Baixos | FCA, CySEC | ✅ Boa opção EU |

---

## Recomendação: OANDA

### Por que OANDA?

1. **API REST v20 moderna** - Fácil integração com Python
2. **SDK Python oficial** - `oandapyV20` no PyPI
3. **Conta Demo gratuita** - Testar sem risco (igual Binance Testnet)
4. **Dados históricos desde 2005** - Ótimo para backtesting
5. **Sem taxa de API** - Custo zero
6. **Spreads competitivos** - EUR/USD ~1.1 pips
7. **Regulação forte** - FCA (UK), CFTC (US)

### Pares Forex Recomendados

| Par | Volatilidade | Spread | Melhor Horário (UTC) |
|-----|--------------|--------|---------------------|
| EUR/USD | Baixa | ~1.1 pip | 07:00-16:00 |
| GBP/USD | Média | ~1.4 pip | 07:00-16:00 |
| USD/JPY | Baixa | ~1.2 pip | 00:00-09:00, 12:00-16:00 |
| AUD/USD | Média | ~1.3 pip | 22:00-07:00 |
| USD/CAD | Média | ~1.8 pip | 12:00-21:00 |

---

## Arquitetura de Integração

```
┌─────────────────────────────────────────────────────────────┐
│                 INTELLIGENT TRADING BOT                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Binance   │    │    OANDA    │    │   Future    │     │
│  │   Adapter   │    │   Adapter   │    │   Broker    │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         │                  │                  │             │
│         └────────┬─────────┴─────────┬────────┘             │
│                  │                   │                      │
│           ┌──────▼──────┐    ┌───────▼───────┐             │
│           │   Unified   │    │   Download    │             │
│           │   Trader    │    │   Manager     │             │
│           └──────┬──────┘    └───────┬───────┘             │
│                  │                   │                      │
│           ┌──────▼───────────────────▼──────┐              │
│           │        Core ML Engine           │              │
│           │  (Features, Labels, Training)   │              │
│           └──────┬───────────────────┬──────┘              │
│                  │                   │                      │
│           ┌──────▼──────┐    ┌───────▼───────┐             │
│           │   Signal    │    │   Threshold   │             │
│           │  Generator  │    │   Optimizer   │             │
│           └─────────────┘    └───────────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementação: Fases

### Fase 1: Setup OANDA (1-2 dias)

1. **Criar conta OANDA Demo**
   - Acessar: https://www.oanda.com/demo-account/
   - Gerar API token no portal

2. **Instalar SDK**
   ```bash
   pip install oandapyV20
   ```

3. **Testar conexão**
   ```python
   from oandapyV20 import API
   import oandapyV20.endpoints.accounts as accounts

   api = API(access_token="YOUR_TOKEN", environment="practice")
   r = accounts.AccountList()
   api.request(r)
   print(r.response)
   ```

### Fase 2: Adapter OANDA (2-3 dias)

Criar `service/adapters/oanda_adapter.py`:

```python
class OandaAdapter:
    """Adapter para OANDA API - mesma interface do Binance."""

    def __init__(self, api_key: str, account_id: str, practice: bool = True):
        self.api = API(
            access_token=api_key,
            environment="practice" if practice else "live"
        )
        self.account_id = account_id

    def get_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        """Baixar candles históricos."""
        # Mapear interval: 1h -> H1, 1d -> D, etc
        pass

    def get_ticker_price(self, symbol: str) -> float:
        """Preço atual."""
        pass

    def create_order(self, symbol: str, side: str, quantity: float) -> dict:
        """Criar ordem."""
        pass

    def get_open_positions(self) -> list:
        """Listar posições abertas."""
        pass
```

### Fase 3: Download & Features (1-2 dias)

1. **Criar script de download Forex**
   ```bash
   python -m scripts.download_oanda -c configs/forex_eurusd_1h.jsonc
   ```

2. **Adaptar features para Forex**
   - Mesmos indicadores técnicos (RSI, SMA, ATR)
   - Adicionar: sessões de mercado (Asia, London, NY)
   - Adicionar: calendário econômico (opcional)

### Fase 4: Config Forex (1 dia)

Criar `configs/forex_eurusd_1h.jsonc`:

```jsonc
{
  "venue": "oanda",
  "symbol": "EUR_USD",
  "freq": "H1",
  "data_folder": "./DATA_FOREX_1h",

  // Forex tem menos volatilidade, ajustar labels
  "label_sets": [
    {
      "generator": "highlow2",
      "config": {
        "thresholds": [0.3],  // 0.3% vs 2% em crypto
        "horizon": 24
      }
    }
  ],

  // Thresholds mais baixos para Forex
  "signal_sets": [
    {
      "generator": "threshold_rule",
      "config": {
        "buy_signal_threshold": 0.005,   // vs 0.02 em crypto
        "sell_signal_threshold": -0.005
      }
    }
  ]
}
```

### Fase 5: Trading Live (1 dia)

1. **Criar trader Forex**
   ```python
   # outputs/trader_oanda.py
   class OandaTrader:
       def execute_signal(self, signal: dict):
           # Similar ao trader_binance_futures.py
           pass
   ```

2. **Integrar ao monitor**
   - Mesmo `trade_monitor.py` com adapter diferente

---

## Diferenças Crypto vs Forex

| Aspecto | Crypto (Binance) | Forex (OANDA) |
|---------|------------------|---------------|
| Símbolo | `BTCUSDT` | `EUR_USD` |
| Horário | 24/7 | 24/5 (fecha domingo) |
| Volatilidade típica | 2-5% dia | 0.3-1% dia |
| Leverage máximo | 125x | 50x (regulado) |
| Spread | 0.01-0.1% | 0.01% (1 pip) |
| Label threshold | 2% | 0.3% |
| Signal threshold | 0.02 | 0.005 |

---

## Cronograma Estimado

| Fase | Duração | Dependência |
|------|---------|-------------|
| 1. Setup OANDA | 1-2 dias | Nenhuma |
| 2. Adapter | 2-3 dias | Fase 1 |
| 3. Download & Features | 1-2 dias | Fase 2 |
| 4. Config | 1 dia | Fase 3 |
| 5. Trading Live | 1 dia | Fase 4 |
| **Total** | **6-9 dias** | |

---

## Próximos Passos Imediatos

1. [ ] Criar conta OANDA Demo: https://www.oanda.com/demo-account/
2. [ ] Gerar API token
3. [ ] Adicionar ao `.env.dev`:
   ```
   OANDA_API_KEY=your_token_here
   OANDA_ACCOUNT_ID=your_account_id
   ```
4. [ ] Rodar: `pip install oandapyV20`

---

## Referências

- [OANDA v20 API Docs](https://developer.oanda.com/rest-live-v20/introduction/)
- [oandapyV20 Python SDK](https://github.com/hootnot/oanda-api-v20)
- [Best Forex Brokers with API](https://www.forexbrokers.com/guides/best-api-brokers)
- [API Trading Comparison](https://www.brokernotes.co/best-forex-brokers-api-trading)
