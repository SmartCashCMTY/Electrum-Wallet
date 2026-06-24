# Electrum-SMART 3.0.0

SmartCash 3.0.0 lightweight thin client wallet.

## What It Does
- SPV wallet for SmartCash 3.0.0
- Connects to ElectrumX servers (no full blockchain download)
- Supports SmartNode operations
- Hardware wallet support (Trezor, Ledger, KeepKey)

## Quick Start

### Windows
```batch
python -m venv venv
venv\Scripts\activate
pip install ecdsa pyaes qrcode pbkdf2 jsonrpclib pysocks pycryptodomex PyQt5
python electrum-smart
```

### Linux
```bash
./run-electrum.sh
```

## System Requirements
- Python 3.7+
- 100 MB disk space
- Internet connection

## Servers (auto-failover)
- 151.252.59.32:50001 (TCP) / 50002 (SSL)
- 151.252.59.33:50001 (TCP) / 50002 (SSL)

## Credits
Original SmartCash Project: https://github.com/SmartCash
ElectrumX by Neil Booth / kyuupichan
This repository is an Update 3.0.0 based on the open-source work of the SmartCash community.

## License
MIT License - see LICENSE file

## Disclaimer
This software is provided "as is", without warranty of any kind. Use at your own risk.

## Security
- Keep your system updated with security patches
- Use firewall to restrict access to necessary ports only
- Never expose RPC ports to the internet
- Use strong, unique passwords

Automatic security updates:
```bash
sudo bash auto-updates-setup.sh
```
Configures unattended-upgrades every 14 days.
