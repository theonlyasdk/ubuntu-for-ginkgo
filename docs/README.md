# Documentation

**Language:** English
This directory contains user guides and engineering records for running mainline Linux on the Xiaomi Redmi Note 8 (ginkgo).

---

## Getting Started (User Guides)

| Document | Purpose |
|----------|---------|
| [install-guide.md](install-guide.md) | Complete step-by-step installation guide from scratch |
| [flash-guide.md](flash-guide.md) | Fastboot command cheat sheet for flashing and updating |
| [known-issues.md](known-issues.md) | Open bugs and missing features, with evidence and fix paths |
| [AGENTS.md](../AGENTS.md) | Operational reference: SSH commands, services, and architecture |

---

## Engineering Audit Records & History

Deep technical investigation logs and milestone bring-up chronicles have been moved to the [audit](audit/) folder:

| Document | Topic |
|----------|-------|
| [audit/ginkgo-mainline-bringup-chronicle.md](audit/ginkgo-mainline-bringup-chronicle.md) | Full hardware bring-up chronicle |
| [audit/ginkgo-wifi-complete-2026-08-18.md](audit/ginkgo-wifi-complete-2026-08-18.md) | WCN3990 ath10k Wi-Fi bring-up details |
| [audit/ginkgo-display-complete-2026-08-17.md](audit/ginkgo-display-complete-2026-08-17.md) | Tianma DSI display driver bring-up |
| [audit/ginkgo-touch-complete-2026-08-17.md](audit/ginkgo-touch-complete-2026-08-17.md) | Novatek NT36672A SPI touch controller |
| [audit/ginkgo-journey-to-remote-ssh.md](audit/ginkgo-journey-to-remote-ssh.md) | USB RNDIS gadget and SSH channel setup |
| [audit/ginkgo-usb-ttl-uart.md](audit/ginkgo-usb-ttl-uart.md) | 1.8V hardware UART wiring instructions |
| [audit/mainline-ginkgo-porting-guide.md](audit/mainline-ginkgo-porting-guide.md) | Hardware mapping and kernel porting overview |
| [audit/postmarketOS-ginkgo-research.md](audit/postmarketOS-ginkgo-research.md) | postmarketOS community research notes |

---

## Other Resources

- [firmware/ginkgo](../firmware/ginkgo/README.md): Extracted device firmware notes
- [reference](../reference/README.md): Reference device trees and schematics
- [backup/ginkgo](../backup/ginkgo/README.md): Partition backup notes
