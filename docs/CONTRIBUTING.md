# Contributing - Intelligent Trading Bot

## Workflow Overview

Este projeto segue um workflow estruturado para separar diferentes tipos de trabalho.

```
┌─────────────────────────────────────────────────────────────────┐
│                        WORKFLOW                                  │
├─────────────────────────────────────────────────────────────────┤
│  Monday.com Board  ←→  GitHub Issues  ←→  Pull Requests        │
│       (Plan)              (Track)           (Execute)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Work Types

| Type | Label | Branch Prefix | Exemplo |
|------|-------|---------------|---------|
| 🔧 DevOps | `devops` | `infra/` | `infra/add-keyvault` |
| 🚀 Feature | `feature` | `feature/` | `feature/multi-symbol` |
| 🐛 Bug Fix | `bug` | `fix/` | `fix/config-loading` |
| 🔬 R&D/ML | `research` | `experiment/` | `experiment/lgbm-tuning` |

---

## Branch Strategy

```
dev (default branch)
│
├── feature/xxx      → New features
├── fix/xxx          → Bug fixes
├── infra/xxx        → Infrastructure changes
├── experiment/xxx   → R&D / ML experiments
│
└── staging          → Shadow mode testing
    └── prod         → (future) Live trading
```

### Regras

1. **Sempre crie branch a partir do `dev`**
2. **Nunca commite direto no `dev` ou `main`**
3. **PRs requerem review (mesmo sendo solo dev, revise seu próprio código)**
4. **Experimentos podem ser mais relaxados** - use `experiment/` prefix

---

## Weekly Workflow (Sugestão)

```
┌─────────────┬──────────────────────────────────────┐
│ Dia         │ Foco                                 │
├─────────────┼──────────────────────────────────────┤
│ Segunda     │ 🔧 DevOps - Infra, CI/CD, Terraform  │
│ Terça       │ 🔧 DevOps - Continuação              │
│ Quarta      │ 🚀 Development - Features, bugs      │
│ Quinta      │ 🚀 Development - Continuação         │
│ Sexta       │ 🔬 R&D - ML experiments, análise     │
│ Sábado      │ 📊 Review - Métricas, planejamento   │
└─────────────┴──────────────────────────────────────┘
```

---

## Creating Issues

Use os templates disponíveis:

- **🔧 DevOps Task** - Infra, CI/CD, cloud
- **🚀 Feature Request** - Novas funcionalidades
- **🐛 Bug Report** - Problemas encontrados
- **🔬 R&D / ML Experiment** - Experimentos, análise

### Labels Obrigatórios

Toda issue deve ter:
1. **Tipo**: `devops`, `feature`, `bug`, ou `research`
2. **Prioridade**: `priority: critical/high/medium/low`
3. **Ambiente**: `env: dev/staging/prod`

---

## Pull Request Process

1. **Crie a issue primeiro** (ou use Monday.com)
2. **Crie branch com prefixo correto**
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-feature
   ```
3. **Faça commits pequenos e descritivos**
   ```bash
   git commit -m "feat: add multi-symbol support"
   git commit -m "fix: correct config loading"
   git commit -m "infra: add key vault terraform"
   ```
4. **Push e crie PR**
   ```bash
   git push -u origin feature/my-feature
   ```
5. **Preencha o template do PR**
6. **Self-review antes de merge**

---

## Commit Messages

Siga o padrão [Conventional Commits](https://conventionalcommits.org):

```
<type>: <description>

[optional body]

[optional footer]
```

### Types

| Type | Descrição |
|------|-----------|
| `feat` | Nova feature |
| `fix` | Bug fix |
| `infra` | Infraestrutura |
| `docs` | Documentação |
| `refactor` | Refatoração |
| `test` | Testes |
| `chore` | Manutenção |
| `experiment` | ML experiment |

### Exemplos

```bash
feat: add LightGBM support for ETHUSDT
fix: correct JSON loading in config parser
infra: add Azure Key Vault for secrets
docs: update INFRA.md with new resources
experiment: test new feature engineering approach
```

---

## Monday.com Integration

### Setup

1. Vá em Monday.com → Integrations → GitHub
2. Conecte o repositório `intelligent-trading-bot`
3. Configure automações:
   - Item criado → Cria Issue no GitHub
   - Status muda para "Done" → Fecha Issue

### Board Structure

```
📋 Backlog
│
├── 🔧 DevOps
│   ├── Item 1
│   └── Item 2
│
├── 🚀 Development
│   └── Item 3
│
└── 🔬 R&D
    └── Item 4

🔄 Sprint Atual (2 semanas)
├── In Progress
├── Review
└── Done

✅ Completed
```

---

## Environments

| Ambiente | Uso | Config |
|----------|-----|--------|
| `dev` | Desenvolvimento, treino | `*_dev.jsonc` |
| `staging` | Shadow mode, validação | `*_staging_v2.jsonc` |
| `prod` | (futuro) Live trading | `*_prod.jsonc` |

---

## Comandos Úteis

```bash
# Setup
make setup

# Validate configs
make validate-configs

# Run pipeline
make dev-1m
make dev-5m

# Staging (shadow mode)
make staging-1m

# Upload to Azure
make upload-1m VERSION=v2025-12-07

# Terraform
make infra-dev-apply
```

---

## Quality Checklist

Antes de fazer merge, verifique:

- [ ] Código funciona localmente
- [ ] Configs validados (`make validate-configs`)
- [ ] CI/CD passou
- [ ] Sem secrets/credentials no código
- [ ] Documentação atualizada (se necessário)
- [ ] Issue relacionada linkada no PR

---

## Dúvidas?

- Verifique a documentação em `infra/azure/terraform/envs/dev/INFRA.md`
- Abra uma issue com dúvidas
