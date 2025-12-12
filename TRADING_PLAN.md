# Trading Plan - Intelligent Trading Bot

> יום רווחי, הפסדי או ניטרלי הוא יום טוב כל עוד נצמדתי לתוכנית המסחר
> "Um dia lucrativo, de perda ou neutro é um bom dia desde que segui o plano de trading"

## Métricas de Sucesso

**NÃO medimos por:** Lucro/Perda diária
**MEDIMOS por:** Aderência ao plano

---

## Regras do Sistema

### 1. Entrada de Posições
- [ ] Seguir sinais ML (trade_score do modelo treinado)
- [ ] buy_signal = True → LONG
- [ ] sell_signal = True → SHORT
- [ ] Não entrar sem sinal ML

### 2. Gestão de Risco
- [ ] Máximo 8% do equity por posição
- [ ] Leverage máximo: 5x (exceto XRP existente 10x)
- [ ] Stop Loss obrigatório em todas posições
- [ ] Máximo 7 posições simultâneas

### 3. Saída de Posições
- [ ] Sair quando sinal ML inverter
- [ ] Sair se stop loss atingido
- [ ] Não sair por emoção/medo/ganância

### 4. Operacional Diário
- [ ] Verificar sinais ML 1x/dia (manhã)
- [ ] Sync dados para Azure 1x/dia
- [ ] Registrar todas operações no log
- [ ] Review semanal de aderência

---

## Checklist Diário

### Manhã
- [ ] Rodar `make bot-status` - verificar posições
- [ ] Analisar sinais ML em DATA_ITB_*/*/signals_*.csv
- [ ] Ajustar posições conforme sinais (se necessário)
- [ ] Registrar decisões no log

### Noite
- [ ] Rodar `make azure-sync` - backup dados
- [ ] Verificar PnL (apenas para registro, não para decisões)
- [ ] Atualizar log de aderência

---

## Log de Aderência

| Data | Seguiu Plano? | Notas |
|------|---------------|-------|
| 2025-12-12 | ✅ | Setup inicial, 7 posições baseadas em ML |

---

## Posições Atuais (2025-12-12)

| Symbol | Direction | ML Signal | Alinhado? |
|--------|-----------|-----------|-----------|
| XRP | LONG | SELL (-0.056) | ❌ (manter por lucro existente) |
| BTC | SHORT | SELL (-0.016) | ✅ |
| ETH | SHORT | SELL (-0.041) | ✅ |
| SOL | SHORT | SELL (-0.116) | ✅ |
| LINK | SHORT | N/A | ⚠️ (sem dados ML) |
| BNB | LONG | BUY (+0.048) | ✅ |
| DOGE | LONG | BUY (+0.029) | ✅ |

**Aderência: 5/7 posições alinhadas com ML**

---

## Comandos Úteis

```bash
# Status do bot
make bot-status

# Sinais ML atuais
python3 -c "
import pandas as pd
for sym in ['BTCUSDT','ETHUSDT','XRPUSDT','SOLUSDT','BNBUSDT','DOGEUSDT']:
    df = pd.read_csv(f'DATA_ITB_1h/{sym}/signals_conservative.csv')
    last = df.iloc[-1]
    print(f'{sym}: score={last[\"trade_score\"]:.3f} buy={last[\"buy_signal\"]} sell={last[\"sell_signal\"]}')
"

# Sync para Azure
make azure-sync

# Dry run (ver o que seria sincronizado)
make azure-sync-dry
```
