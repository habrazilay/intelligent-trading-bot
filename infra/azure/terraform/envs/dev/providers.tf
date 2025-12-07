terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.50"
    }
  }
}

provider "azurerm" {
  features {}

  subscription_id = "2f6db364-4841-4db8-ad62-b53c2c906b0b"
}