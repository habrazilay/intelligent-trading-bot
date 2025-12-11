#!/usr/bin/env python3
"""
Cloud Cost Monitor

Tracks spending on GCP and Azure in real-time.
Alerts when approaching budget limits.

Usage:
    # Check current costs
    python scripts/cloud_cost_monitor.py

    # Set budget alert
    python scripts/cloud_cost_monitor.py --budget 200 --alert-at 50,100,150

    # Monitor continuously (check every hour)
    python scripts/cloud_cost_monitor.py --monitor --interval 3600
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
import subprocess


def check_gcp_costs():
    """Check GCP costs using gcloud CLI"""
    print("\n💰 GCP Costs:")
    print("=" * 60)

    # Check if gcloud is installed
    if subprocess.run(["which", "gcloud"], capture_output=True).returncode != 0:
        print("   ⚠️  gcloud CLI not installed")
        return None

    # Get project
    result = subprocess.run(
        ["gcloud", "config", "get-value", "project"],
        capture_output=True, text=True
    )
    project = result.stdout.strip()

    if not project or project == "(unset)":
        print("   ⚠️  No project set")
        return None

    print(f"   Project: {project}")

    # Get billing account
    result = subprocess.run(
        ["gcloud", "billing", "accounts", "list", "--format=value(name)"],
        capture_output=True, text=True
    )
    billing_account = result.stdout.strip().split('\n')[0] if result.stdout else None

    if not billing_account:
        print("   ⚠️  No billing account found")
        return None

    print(f"   Billing Account: {billing_account}")

    # Try to get current month costs
    # Note: This requires billing export to BigQuery to be set up
    print("\n   Current Month Costs:")
    print("   ⚠️  For detailed costs, go to:")
    print("   https://console.cloud.google.com/billing")

    # Alternative: Show compute instances (main cost driver)
    print("\n   Active Compute Instances:")
    result = subprocess.run(
        ["gcloud", "compute", "instances", "list", "--format=table(name,zone,machineType,status)"],
        capture_output=True, text=True
    )

    if result.returncode == 0 and result.stdout:
        print(result.stdout)
    else:
        print("   No active instances")

    return {
        'project': project,
        'billing_account': billing_account,
        'has_active_vms': bool(result.stdout)
    }


def check_azure_costs():
    """Check Azure costs using az CLI"""
    print("\n💰 Azure Costs:")
    print("=" * 60)

    # Check if az is installed
    if subprocess.run(["which", "az"], capture_output=True).returncode != 0:
        print("   ⚠️  Azure CLI not installed")
        return None

    # Check login
    result = subprocess.run(
        ["az", "account", "show", "--query", "name", "-o", "tsv"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print("   ⚠️  Not logged in (run: az login)")
        return None

    subscription = result.stdout.strip()
    print(f"   Subscription: {subscription}")

    # Get current month costs
    today = datetime.now()
    start_date = today.replace(day=1).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')

    print(f"\n   Costs from {start_date} to {end_date}:")

    result = subprocess.run([
        "az", "consumption", "usage", "list",
        "--start-date", start_date,
        "--end-date", end_date,
        "--query", "[].{Service:meterCategory, Cost:pretaxCost}",
        "-o", "table"
    ], capture_output=True, text=True)

    if result.returncode == 0 and result.stdout:
        print(result.stdout)
    else:
        print("   No usage data available")

    # Show active VMs
    print("\n   Active Virtual Machines:")
    result = subprocess.run([
        "az", "vm", "list",
        "--query", "[].{Name:name, ResourceGroup:resourceGroup, Location:location, Size:hardwareProfile.vmSize}",
        "-o", "table"
    ], capture_output=True, text=True)

    if result.returncode == 0 and result.stdout:
        print(result.stdout)
    else:
        print("   No active VMs")

    return {
        'subscription': subscription,
        'has_active_vms': bool(result.stdout)
    }


def estimate_running_costs(gcp_info, azure_info):
    """Estimate hourly costs based on active resources"""
    print("\n⏰ Estimated Hourly Costs:")
    print("=" * 60)

    hourly_cost = 0.0

    # GCP estimates
    if gcp_info and gcp_info.get('has_active_vms'):
        print("   ⚠️  GCP has active VMs!")
        print("   Common VM costs:")
        print("      - n1-standard-4: $0.19/hour")
        print("      - n1-standard-4 + T4 GPU: $0.54/hour")
        print("      - n1-standard-4 + V100 GPU: $2.67/hour")
        print("\n   Check actual costs at:")
        print("   https://console.cloud.google.com/compute/instances")

    # Azure estimates
    if azure_info and azure_info.get('has_active_vms'):
        print("\n   ⚠️  Azure has active VMs!")
        print("   Common VM costs:")
        print("      - Standard_D4s_v3: $0.192/hour")
        print("      - NC6 (with GPU): $0.90/hour")
        print("      - NC6s_v3 (with V100): $3.06/hour")

    if not (gcp_info and gcp_info.get('has_active_vms')) and \
       not (azure_info and azure_info.get('has_active_vms')):
        print("   ✅ No active VMs - No hourly costs!")


def check_budget(budget, spent, alert_thresholds):
    """Check if spending is approaching budget limits"""
    print(f"\n📊 Budget Status:")
    print("=" * 60)

    if spent is None:
        print("   ⚠️  Cannot determine spending")
        print("   Please check billing console manually")
        return

    percentage = (spent / budget) * 100

    print(f"   Budget: ${budget:.2f}")
    print(f"   Spent: ${spent:.2f}")
    print(f"   Remaining: ${budget - spent:.2f}")
    print(f"   Used: {percentage:.1f}%")

    # Check alerts
    for threshold in sorted(alert_thresholds):
        if spent >= threshold:
            print(f"\n   🚨 ALERT: Spent ${spent:.2f} (threshold: ${threshold:.2f})")


def monitor_loop(interval=3600, budget=None, alert_thresholds=None):
    """Monitor costs continuously"""
    print(f"\n🔄 Starting cost monitoring (checking every {interval/60:.0f} minutes)")
    print("   Press Ctrl+C to stop\n")

    try:
        while True:
            print("\n" + "=" * 60)
            print(f"Check at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)

            gcp_info = check_gcp_costs()
            azure_info = check_azure_costs()
            estimate_running_costs(gcp_info, azure_info)

            if budget and alert_thresholds:
                # TODO: Get actual spending from billing API
                check_budget(budget, None, alert_thresholds)

            print(f"\n⏰ Next check in {interval/60:.0f} minutes...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped")


def show_cost_optimization_tips():
    """Show tips to reduce costs"""
    print("\n💡 Cost Optimization Tips:")
    print("=" * 60)
    print("""
1. DELETE unused VMs immediately:
   gcloud compute instances delete INSTANCE_NAME
   az vm delete --resource-group GROUP --name VM_NAME

2. Use PREEMPTIBLE/SPOT instances (60-80% cheaper):
   gcloud compute instances create ... --preemptible
   az vm create ... --priority Spot

3. Use CHEAPEST region:
   GCP: us-central1 (Iowa)
   Azure: eastus

4. STOP VMs when not using:
   NOTE: Stopped VMs still charge for disk!
   Better to DELETE and recreate

5. Set BUDGET ALERTS:
   GCP: console.cloud.google.com/billing/budgets
   Azure: portal.azure.com → Cost Management → Budgets

6. Use FREE TIER resources:
   - BigQuery: 1 TB queries/month (free)
   - Cloud Storage: 5 GB (free)
   - f1-micro instance: 1 instance/month (free)

7. Monitor DAILY:
   python scripts/cloud_cost_monitor.py
    """)


def main():
    parser = argparse.ArgumentParser(
        description='Monitor cloud costs (GCP and Azure)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check current costs
  python scripts/cloud_cost_monitor.py

  # Set budget with alerts
  python scripts/cloud_cost_monitor.py --budget 200 --alert-at 50,100,150

  # Monitor continuously (check every hour)
  python scripts/cloud_cost_monitor.py --monitor --interval 3600

  # Show cost optimization tips
  python scripts/cloud_cost_monitor.py --tips
        """
    )

    parser.add_argument(
        '--budget',
        type=float,
        help='Total budget in USD'
    )

    parser.add_argument(
        '--alert-at',
        type=str,
        help='Alert thresholds (comma-separated, e.g., 50,100,150)'
    )

    parser.add_argument(
        '--monitor',
        action='store_true',
        help='Monitor continuously'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=3600,
        help='Monitoring interval in seconds (default: 3600 = 1 hour)'
    )

    parser.add_argument(
        '--tips',
        action='store_true',
        help='Show cost optimization tips'
    )

    args = parser.parse_args()

    # Show tips and exit
    if args.tips:
        show_cost_optimization_tips()
        return

    # Parse alert thresholds
    alert_thresholds = []
    if args.alert_at:
        alert_thresholds = [float(x) for x in args.alert_at.split(',')]

    # Monitor mode
    if args.monitor:
        monitor_loop(args.interval, args.budget, alert_thresholds)
        return

    # One-time check
    gcp_info = check_gcp_costs()
    azure_info = check_azure_costs()
    estimate_running_costs(gcp_info, azure_info)

    if args.budget and alert_thresholds:
        # TODO: Get actual spending from billing API
        print("\n⚠️  Budget tracking requires billing export setup")
        print("   See: https://cloud.google.com/billing/docs/how-to/export-data-bigquery")

    # Always show tips at the end
    show_cost_optimization_tips()


if __name__ == '__main__':
    main()
