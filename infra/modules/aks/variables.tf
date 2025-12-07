variable "prefix"        { type = string }
variable "location"      { type = string }
variable "rg_name"       { type = string }
variable "sku_tier"      { type = string  default = "Free" }
variable "node_count"    { type = number  default = 1 }
variable "vm_size"       { type = string  default = "Standard_D2as_v5" }
variable "spot_enabled"  { type = bool    default = true }
variable "spot_count"    { type = number  default = 2 }
variable "admin_username"{ type = string  default = null }
variable "ssh_public_key"{ type = string  default = null }
variable "law_id"        { type = string }
variable "tags"          { type = map(string) default = {} }