variable "location" {
  type    = string
  default = "eastus"
}

variable "project_name" {
  type    = string
  default = "itb-btcusdt-1m"
}

variable "image_tag" {
  type        = string
  description = "Tag completa da imagem Docker (ex: itbacr.azurecr.io/itb-btcusdt-1m:sha-xxxx)"
}