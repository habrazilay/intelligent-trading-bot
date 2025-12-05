	•	nome do Resource Group
	•	nome do Storage Account
	•	nomes dos File Shares (data-itb-1m, data-itb-5m, data-itb-1h)
	•	nome do ACR (itbacr.azurecr.io)
	•	comandos Terraform que você roda às vezes:
cd infra/azure/terraform/envs/dev
terraform plan
terraform apply

### Backup

- Recovery Services Vault: `vault697` (rg-itb-dev, eastus)
- Policy: `itb-backup-1m-5m-1h`
  - Frequency: Daily @ 19:30 UTC
  - Retention: 30 days
- Protected shares:
  - `data-itb-1m`
  - `data-itb-5m`
  - `data-itb-1h`