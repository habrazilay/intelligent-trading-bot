# =============================================================================
# Azure VM for Data Collection (Orderbook + Klines)
# =============================================================================
# This VM runs 24/7 collecting data from Binance with a static IP
# that you can whitelist in your Binance API settings.
#
# Cost estimate: ~$15-30/month for B1s (1 vCPU, 1GB RAM)
# =============================================================================

# -----------------------------------------------------------------------------
# Network: Public IP (Static)
# -----------------------------------------------------------------------------

resource "azurerm_public_ip" "collector" {
  name                = "pip-collector-${var.project_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"

  tags = {
    environment = "dev"
    purpose     = "binance-data-collection"
  }
}

# -----------------------------------------------------------------------------
# Network: Virtual Network + Subnet
# -----------------------------------------------------------------------------

resource "azurerm_virtual_network" "collector" {
  name                = "vnet-collector-${var.project_name}"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_subnet" "collector" {
  name                 = "snet-collector"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.collector.name
  address_prefixes     = ["10.0.1.0/24"]
}

# -----------------------------------------------------------------------------
# Network: Network Security Group (SSH only from your IP)
# -----------------------------------------------------------------------------

resource "azurerm_network_security_group" "collector" {
  name                = "nsg-collector-${var.project_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "SSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"  # TODO: Restrict to your IP
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowOutbound"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# -----------------------------------------------------------------------------
# Network: Network Interface
# -----------------------------------------------------------------------------

resource "azurerm_network_interface" "collector" {
  name                = "nic-collector-${var.project_name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.collector.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.collector.id
  }
}

resource "azurerm_network_interface_security_group_association" "collector" {
  network_interface_id      = azurerm_network_interface.collector.id
  network_security_group_id = azurerm_network_security_group.collector.id
}

# -----------------------------------------------------------------------------
# VM: Linux Virtual Machine
# -----------------------------------------------------------------------------

resource "azurerm_linux_virtual_machine" "collector" {
  name                = "vm-collector-${var.project_name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = var.collector_vm_size
  admin_username      = "azureuser"

  network_interface_ids = [
    azurerm_network_interface.collector.id,
  ]

  admin_ssh_key {
    username   = "azureuser"
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 64
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }

  # Cloud-init script to setup the collector
  custom_data = base64encode(<<-EOF
    #!/bin/bash
    set -e

    # Update system
    apt-get update
    apt-get upgrade -y

    # Install Python and dependencies
    apt-get install -y python3 python3-pip python3-venv git

    # Create app directory
    mkdir -p /opt/itb
    cd /opt/itb

    # Clone repo (or you can use Azure File Share)
    git clone https://github.com/your-repo/intelligent-trading-bot.git .

    # Create virtual environment
    python3 -m venv .venv
    source .venv/bin/activate

    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt

    # Create systemd service for orderbook collector
    cat > /etc/systemd/system/itb-orderbook.service << 'SERVICEEOF'
    [Unit]
    Description=ITB Orderbook Collector
    After=network.target

    [Service]
    Type=simple
    User=azureuser
    WorkingDirectory=/opt/itb
    Environment="PATH=/opt/itb/.venv/bin"
    ExecStart=/opt/itb/.venv/bin/python scripts/collect_orderbook.py --symbol BTCUSDT,ETHUSDT,XRPUSDT,BNBUSDT,SOLUSDT --duration 365d --save-interval 30m
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
    SERVICEEOF

    # Enable and start service
    systemctl daemon-reload
    systemctl enable itb-orderbook
    # Don't start yet - needs credentials

    echo "VM setup complete! Configure credentials and start service."
  EOF
  )

  tags = {
    environment = "dev"
    purpose     = "binance-data-collection"
  }
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "collector_vm_public_ip" {
  description = "Public IP of the collector VM - add this to Binance whitelist"
  value       = azurerm_public_ip.collector.ip_address
}

output "collector_vm_ssh_command" {
  description = "SSH command to connect to the VM"
  value       = "ssh azureuser@${azurerm_public_ip.collector.ip_address}"
}
