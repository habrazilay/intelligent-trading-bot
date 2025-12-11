# 🐋 Docker Guide - Intelligent Trading Bot

## 📊 Image Sizes

| Image | Size | Use Case |
|-------|------|----------|
| `itb:minimal` | ~400MB | **Production** - Shadow mode, predictions |
| `itb:train` | ~600MB | **Training** - Model training in Azure/GCP |
| `itb:full` | ~1.1GB | **Development** - Local development with all deps |

---

## 🏗️ Building Images

### Production (Minimal) - Recommended for Shadow Mode
```bash
docker build --target production -t itb:minimal .
```

**Includes:**
- ✅ Core ML libraries (scikit-learn, lightgbm)
- ✅ TA-Lib (compiled from source)
- ✅ Binance API
- ✅ All prediction scripts
- ❌ NO TensorFlow (saves 500MB)
- ❌ NO Google Cloud libraries (saves 150MB)

---

### Training - For Azure Pipeline
```bash
docker build --target training -t itb:train .
```

**Includes:**
- Everything from `minimal` +
- ✅ Training dependencies (numba, dateparser)
- ❌ NO TensorFlow
- ❌ NO Google Cloud

---

### Full - For Local Development
```bash
docker build --target full -t itb:full .
```

**Includes:**
- Everything from `training` +
- ✅ TensorFlow (for LSTM experiments)
- ✅ Google Cloud Platform libraries
- ✅ All optional dependencies

---

## 🚀 Running Containers

### Shadow Mode (Production)

```bash
# Run output.py (predictions + trading)
docker run -v $(pwd)/DATA_ITB_5m:/app/DATA_ITB_5m \
  -v $(pwd)/.env:/app/.env \
  itb:minimal \
  python -m scripts.output \
    -c configs/base_conservative.jsonc \
    --symbol BTCUSDT --freq 5m
```

### Complete Pipeline (Training)

```bash
# Run full pipeline: download → train → backtest
docker run -v $(pwd):/app \
  -e BINANCE_API_KEY="your_key" \
  -e BINANCE_API_SECRET="your_secret" \
  itb:train \
  bash -c "make run SYMBOL=BTCUSDT FREQ=5m"
```

### Individual Scripts

```bash
# Download data
docker run -v $(pwd)/DATA_ITB_5m:/app/DATA_ITB_5m \
  itb:minimal \
  python -m scripts.download_binance \
    -c configs/base_conservative.jsonc --symbol BTCUSDT --freq 5m

# Train models
docker run -v $(pwd)/DATA_ITB_5m:/app/DATA_ITB_5m \
  itb:train \
  python -m scripts.train \
    -c configs/base_conservative.jsonc --symbol BTCUSDT --freq 5m

# Generate predictions
docker run -v $(pwd)/DATA_ITB_5m:/app/DATA_ITB_5m \
  itb:minimal \
  python -m scripts.predict \
    -c configs/base_conservative.jsonc --symbol BTCUSDT --freq 5m
```

---

## 🔧 Docker Compose (Recommended for Shadow Mode)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  itb-shadow:
    image: itb:minimal
    container_name: itb-shadow-mode
    restart: unless-stopped

    volumes:
      - ./DATA_ITB_5m:/app/DATA_ITB_5m
      - ./DATA_ITB_1h:/app/DATA_ITB_1h
      - ./configs:/app/configs
      - ./.env:/app/.env

    environment:
      - PYTHONUNBUFFERED=1
      - TZ=UTC

    command: >
      bash -c "
        while true; do
          python -m scripts.output \
            -c configs/base_conservative.jsonc \
            --symbol BTCUSDT --freq 5m;
          sleep 300;
        done
      "

    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 60s
      timeout: 10s
      retries: 3
```

Run with:
```bash
docker-compose up -d
docker-compose logs -f
```

---

## 📦 CI/CD - GitHub Actions

The Azure pipeline automatically builds and pushes Docker images when you push to `main` or `staging`:

### Automatic Build & Push

```bash
git push origin main
# → Triggers workflow
# → Builds itb:minimal and itb:training
# → Pushes to Docker Hub
```

### Manual Trigger

1. Go to GitHub Actions
2. Select "Azure ML Pipeline"
3. Click "Run workflow"
4. Choose:
   - Symbol: BTCUSDT
   - Freq: 5m
   - Strategy: conservative
   - Mode: full

---

## 🔐 Required Secrets

### For Docker Hub (CI/CD):
- `DOCKER_USERNAME`
- `DOCKER_PASSWORD`

### For Trading:
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `BINANCE_USE_TESTNET=true` (start with testnet!)

### For Notifications:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### For Azure:
- `AZURE_CREDENTIALS`
- `AZURE_STORAGE_ACCOUNT`

---

## 📝 Best Practices

### 1. Use Volumes for Data

**❌ Don't do this:**
```bash
docker build -t itb .  # Includes DATA_* in image
```

**✅ Do this:**
```bash
docker build --target production -t itb:minimal .
docker run -v $(pwd)/DATA_ITB_5m:/app/DATA_ITB_5m itb:minimal ...
```

### 2. Use Minimal Image for Production

```bash
# Shadow mode on server
docker pull username/intelligent-trading-bot:minimal
docker run -d -v /path/to/data:/app/DATA_ITB_5m \
  username/intelligent-trading-bot:minimal \
  python -m scripts.output -c configs/base_conservative.jsonc \
  --symbol BTCUSDT --freq 5m
```

### 3. Environment Variables

Use `.env` file:
```bash
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_USE_TESTNET=true
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

Mount it:
```bash
docker run -v $(pwd)/.env:/app/.env itb:minimal ...
```

---

## 🐛 Troubleshooting

### Image too large?
```bash
# Use minimal target
docker build --target production -t itb:minimal .

# Check size
docker images itb:minimal
# Should be ~400MB
```

### TA-Lib compilation fails?
```bash
# Check builder stage logs
docker build --target builder -t itb:builder .

# If fails, try updating TA-Lib version in Dockerfile
```

### Scripts not found?
```bash
# Make sure PYTHONPATH is set
docker run itb:minimal env | grep PYTHONPATH
# Should show: PYTHONPATH=/app

# Check scripts exist
docker run itb:minimal ls -la scripts/
```

### Permission issues with volumes?
```bash
# Fix permissions
chmod -R 755 DATA_ITB_*/

# Or run with user
docker run -u $(id -u):$(id -g) -v $(pwd):/app itb:minimal ...
```

---

## 📈 Next Steps

1. **Build minimal image** for production
2. **Test locally** with docker-compose
3. **Push to registry** (automatic via CI/CD)
4. **Deploy to Azure** Container Instances
5. **Monitor logs** and adjust thresholds

---

## 🔗 Related Files

- `Dockerfile` - Multi-stage build configuration
- `.dockerignore` - Excluded files from image
- `requirements-minimal.txt` - Production dependencies
- `requirements-train.txt` - Training dependencies
- `requirements-full.txt` - All dependencies
- `.github/workflows/azure-pipeline.yml` - CI/CD pipeline
