# Atualizar infra dev (storage, ACR etc.)
make infra-dev-apply

# Build & push imagem dev
make image-dev

# Rodar pipeline dev 1m
make dev-1m

# Rodar pipeline dev 5m
make dev-5m

# Rodar análise 1m (o analyze_btcusdt_1m.py) em ACI
make analyze-1m
criar um Makefile com alvos tipo:
make tf-dev-plan

make tf-dev-apply
make upload-1m
make upload-5m

make upload-1m
make upload-5m
make upload-1h