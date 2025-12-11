# Guia de Testes - Trading Bot Pipeline

## 🎯 Objetivo

Este guia mostra como **testar todos os scripts localmente** antes de automatizar o CI/CD na Azure.

---

## 📦 Arquivos Criados

Foram criados os seguintes arquivos para facilitar os testes:

| Arquivo | Descrição |
|---------|-----------|
| [test_pipeline_local.sh](test_pipeline_local.sh) | Script automatizado de testes |
| [SCRIPTS_GUIDE.md](SCRIPTS_GUIDE.md) | Guia completo dos scripts (novos vs antigos) |
| [AZURE_SETUP.md](AZURE_SETUP.md) | Guia de configuração Azure + GitHub Actions |
| [setup_azure.sh](setup_azure.sh) | Helper para setup da Azure |
| [.github/workflows/azure-pipeline.yml](.github/workflows/azure-pipeline.yml) | Workflow CI/CD completo |

---

## ⚡ Quick Start (5 minutos)

### 1. Teste Rápido

```bash
# Dar permissão de execução
chmod +x test_pipeline_local.sh

# Executar teste rápido (apenas scripts novos)
./test_pipeline_local.sh --quick
```

**Saída esperada**:
```
╔════════════════════════════════════════════════════════════════╗
║        TESTE LOCAL - INTELLIGENT TRADING BOT PIPELINE         ║
╚════════════════════════════════════════════════════════════════╝

[INFO] Modo de teste: --quick
[INFO] Config: configs/btcusdt_1m_dev.jsonc
[INFO] Log: test_pipeline_20251211_143022.log

=================================================================
  Verificando Dependências
=================================================================
[✓] Python encontrado: Python 3.10.8
[✓] Todos os pacotes Python necessários estão instalados
...
```

### 2. Verificar Resultado

```bash
# Ver relatório final
tail -50 test_pipeline_*.log

# Ou ver tudo
cat test_pipeline_*.log
```

---

## 🧪 Modos de Teste

### Teste Rápido (5 min) - **Recomendado**

```bash
./test_pipeline_local.sh --quick
```

**O que testa**:
- ✅ Scripts novos (`merge_new`, `features_new`, `labels_new`)
- ✅ Orderbook collection (30s)
- ✅ Orderbook verification
- ✅ Training com dados novos
- ✅ Integração básica

**Use quando**: Quer validar rapidamente se os scripts funcionam.

---

### Teste Completo (30 min)

```bash
./test_pipeline_local.sh --full
```

**O que testa**:
- ✅ Pipeline antigo **completo** (8 etapas do README)
- ✅ Scripts novos
- ✅ Integração entre ambos
- ✅ Verificação de arquivos de saída

**Use quando**: Quer garantir 100% que tudo funciona antes do deploy.

---

### Teste Apenas Scripts Novos

```bash
./test_pipeline_local.sh --new-only
```

**O que testa**:
- ✅ `collect_orderbook.py`
- ✅ `verify_orderbook_data.py`
- ✅ `merge_new.py`
- ✅ `features_new.py`
- ✅ `labels_new.py`

**Use quando**: Só quer testar os scripts novos isoladamente.

---

## 📊 Interpretando os Resultados

### Sucesso Total ✅

```
=========================================
  TODOS OS TESTES PASSARAM! ✓
=========================================

Próximos passos:
1. Revise o log: cat test_pipeline_20251211_143022.log
2. Se tudo estiver OK, atualize o CI/CD na Azure
3. Execute: ./scripts/deploy_azure.sh
```

**Ação**: Pode prosseguir para configurar Azure!

---

### Alguns Testes Falharam ❌

```
=========================================
  ALGUNS TESTES FALHARAM! ✗
=========================================

Ações recomendadas:
1. Revise os erros no log: cat test_pipeline_20251211_143022.log
2. Corrija os problemas encontrados
3. Execute novamente: ./test_pipeline_local.sh
```

**Ação**: Revise o log, corrija erros, teste novamente.

---

## 🔍 Verificação Manual

Além do script automatizado, você pode testar manualmente cada script:

### Scripts Novos

```bash
# 1. Collect orderbook (teste de 2 minutos)
python scripts/collect_orderbook.py --symbol BTCUSDT --duration 2m --save-interval 1m

# 2. Verificar orderbook
python scripts/verify_orderbook_data.py

# 3. Merge (dry-run primeiro)
python -m scripts.merge_new -c configs/btcusdt_1m_dev.jsonc --dry-run
python -m scripts.merge_new -c configs/btcusdt_1m_dev.jsonc

# 4. Features (dry-run primeiro)
python -m scripts.features_new -c configs/btcusdt_1m_dev.jsonc --dry-run
python -m scripts.features_new -c configs/btcusdt_1m_dev.jsonc

# 5. Labels (dry-run primeiro)
python -m scripts.labels_new -c configs/btcusdt_1m_dev.jsonc --dry-run
python -m scripts.labels_new -c configs/btcusdt_1m_dev.jsonc

# 6. Train
python -m scripts.train -c configs/btcusdt_1m_dev.jsonc
```

### Scripts Antigos (Pipeline Original)

```bash
# Pipeline completo do README
python -m scripts.download_binance -c configs/btcusdt_1m_dev.jsonc
python -m scripts.merge -c configs/btcusdt_1m_dev.jsonc
python -m scripts.features -c configs/btcusdt_1m_dev.jsonc
python -m scripts.labels -c configs/btcusdt_1m_dev.jsonc
python -m scripts.train -c configs/btcusdt_1m_dev.jsonc
python -m scripts.predict -c configs/btcusdt_1m_dev.jsonc
python -m scripts.signals -c configs/btcusdt_1m_dev.jsonc
python -m scripts.output -c configs/btcusdt_1m_dev.jsonc
```

---

## 🐛 Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'talib'"

**Solução**:
```bash
# macOS
brew install ta-lib
pip install TA-Lib

# Linux
sudo apt-get install ta-lib
pip install TA-Lib
```

### Erro: "Config file not found"

**Solução**: Verificar se o arquivo de config existe
```bash
ls -la configs/btcusdt_1m_dev.jsonc
```

### Erro: "Permission denied"

**Solução**: Dar permissão de execução
```bash
chmod +x test_pipeline_local.sh
chmod +x setup_azure.sh
```

### Erro: "Binance API error"

**Solução**: Verificar `.env`
```bash
# Copiar template
cp .env.sample .env

# Editar e adicionar suas chaves
nano .env
```

### Dados de teste ocupando muito espaço

**Solução**: Limpar dados de teste
```bash
rm -rf DATA_ITB_TEST DATA_ORDERBOOK_TEST
rm -f test_pipeline_*.log
```

---

## 📝 Checklist Pré-Deploy

Antes de configurar o Azure CI/CD, certifique-se:

- [ ] ✅ Teste local passou (`./test_pipeline_local.sh --quick`)
- [ ] ✅ Logs revisados (`cat test_pipeline_*.log`)
- [ ] ✅ Arquivos de saída criados corretamente
- [ ] ✅ `.env` configurado com suas chaves
- [ ] ✅ `requirements.txt` atualizado
- [ ] ✅ Config files validados

---

## 🚀 Próximos Passos

Depois que os testes locais passarem:

### 1. Configurar Azure

```bash
# Verificar status
./setup_azure.sh --check

# Setup completo
./setup_azure.sh --interactive
```

📖 Ver guia completo: [AZURE_SETUP.md](AZURE_SETUP.md)

### 2. Configurar GitHub Secrets

Vá em: **Settings** → **Secrets and variables** → **Actions**

Adicione os secrets:
- `AZURE_CREDENTIALS`
- `AZURE_STORAGE_ACCOUNT`
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 3. Testar Workflow Manualmente

1. Vá em **Actions** → **Azure ML Pipeline**
2. Clique em **Run workflow**
3. Selecione:
   - Branch: `dev`
   - Config: `configs/btcusdt_1m_dev.jsonc`
   - Mode: `quick`

### 4. Automatizar

Depois de validar manualmente:

```bash
# Commit e push no dev
git checkout dev
git add .
git commit -m "feat: setup CI/CD pipeline"
git push

# Se OK, merge para staging
git checkout staging
git merge dev
git push

# Se staging OK, merge para main → deploy automático!
git checkout main
git merge staging
git push
```

---

## 📚 Documentação Completa

- [SCRIPTS_GUIDE.md](SCRIPTS_GUIDE.md) - Guia completo dos scripts (antigos vs novos)
- [AZURE_SETUP.md](AZURE_SETUP.md) - Setup Azure + GitHub Actions
- [README.md](README.md) - Documentação geral do projeto

---

## ❓ FAQ

### 1. Qual a diferença entre scripts antigos e novos?

**Resposta**: Os novos têm melhor logging, suportam `--dry-run` e são otimizados para CI/CD. Veja [SCRIPTS_GUIDE.md](SCRIPTS_GUIDE.md) para detalhes.

### 2. Preciso migrar para os scripts novos?

**Resposta**: Não obrigatório. Os antigos continuam funcionando. Mas para CI/CD é recomendado usar os novos.

### 3. O `collect_orderbook.py` substituí o `download_binance.py`?

**Resposta**: Não! São **complementares**:
- `download_binance.py` → dados históricos OHLCV
- `collect_orderbook.py` → dados de orderbook em tempo real

### 4. Posso usar scripts novos no pipeline antigo?

**Resposta**: Sim! São compatíveis. Exemplo:
```bash
python -m scripts.download_binance -c config.json  # Antigo
python -m scripts.merge_new -c config.json         # Novo
python -m scripts.features_new -c config.json      # Novo
python -m scripts.train -c config.json             # Antigo
```

### 5. O teste local demora quanto tempo?

**Resposta**:
- `--quick`: ~5-10 minutos
- `--full`: ~30-60 minutos
- `--new-only`: ~5 minutos

---

**Última atualização**: 2025-12-11
**Versão**: 1.0

**Precisa de ajuda?** Abra uma issue no GitHub ou consulte a documentação completa.
