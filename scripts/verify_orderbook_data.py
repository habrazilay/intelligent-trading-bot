#!/usr/bin/env python3
"""
Verify Order Book Data Collection

Checks the orderbook data collected and shows statistics.

Usage:
    python scripts/verify_orderbook_data.py
"""

import pandas as pd
from pathlib import Path
import glob

def verify_orderbook_data():
    """Verify collected orderbook data"""

    print("🔍 Verificando dados de order book coletados...\n")

    # Find orderbook files
    orderbook_dir = Path('DATA_ORDERBOOK')

    if not orderbook_dir.exists():
        print(f"❌ Pasta {orderbook_dir} não encontrada!")
        print(f"   Os dados devem estar em: {orderbook_dir.absolute()}")
        return False

    # Find all parquet files
    files = sorted(glob.glob(str(orderbook_dir / "BTCUSDT_orderbook_*.parquet")))

    if not files:
        print(f"❌ Nenhum arquivo encontrado em {orderbook_dir}/")
        return False

    print(f"✅ Encontrados {len(files)} arquivo(s):\n")

    total_rows = 0
    all_data = []

    for i, file in enumerate(files, 1):
        filepath = Path(file)
        df = pd.read_parquet(file)

        file_size_mb = filepath.stat().st_size / 1024 / 1024

        print(f"   {i}. {filepath.name}")
        print(f"      Tamanho: {file_size_mb:.2f} MB")
        print(f"      Linhas: {len(df):,}")

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            print(f"      Período: {df['timestamp'].min()} → {df['timestamp'].max()}")

        print()

        total_rows += len(df)
        all_data.append(df)

    # Summary
    print("="*60)
    print("📊 RESUMO")
    print("="*60)
    print(f"Total de arquivos: {len(files)}")
    print(f"Total de snapshots: {total_rows:,}")
    print(f"Taxa média: {total_rows / (2 * 3600):.2f} snapshots/segundo")

    # Combine all data
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined['timestamp'] = pd.to_datetime(combined['timestamp'])
        combined = combined.sort_values('timestamp')

        print(f"\nPeríodo completo: {combined['timestamp'].min()} → {combined['timestamp'].max()}")

        duration = (combined['timestamp'].max() - combined['timestamp'].min()).total_seconds()
        print(f"Duração: {duration / 3600:.2f} horas")

        # Check columns
        print(f"\nColunas disponíveis: {len(combined.columns)}")
        print(f"   Primeiras 10: {list(combined.columns[:10])}")

        # Show sample
        print(f"\n📋 Amostra dos dados (primeiras 3 linhas):")
        print(combined.head(3).to_string())

        # Check for missing data
        missing = combined.isnull().sum()
        if missing.any():
            print(f"\n⚠️  Dados faltando em algumas colunas:")
            print(missing[missing > 0])
        else:
            print(f"\n✅ Sem dados faltando!")

        return True

    return False


if __name__ == '__main__':
    success = verify_orderbook_data()

    if success:
        print("\n✅ Dados coletados com sucesso!")
        print("\nPróximos passos:")
        print("1. Testar extração de features")
        print("2. Se funcionar → Iniciar coleta de 7 dias")
        print("3. Após 7 dias → Backtest completo")
    else:
        print("\n❌ Verificação falhou. Verifique se a coleta funcionou corretamente.")
