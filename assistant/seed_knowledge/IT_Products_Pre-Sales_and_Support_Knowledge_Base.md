# IT and Office Products - Pre-Sales and Support Knowledge Base

General product knowledge for staff who quote, sell, and support servers, storage, printers, plotters, UPS, network switches, firewalls, operating systems, and related office equipment. These are vendor-neutral guidelines. Always confirm exact specifications, compatibility, availability, and pricing against the vendor datasheet and the latest quotation system before committing to a customer. Company-specific prices, lead times, and warranty terms are not covered here and must come from Sales Operations.

## 1. Servers
- Form factors: tower (small offices, 1 to 25 users, quiet and cheap to start), rack (1U, 2U, 4U for server rooms and data centres, scalable), blade (high density, needs a chassis).
- Key sizing questions: number of users, workloads (file server, ERP, database, virtualisation, email), number of virtual machines, expected growth over 3 to 5 years, and uptime requirements.
- CPU: choose by core count and clock. Per-core software licensing (Windows Server, SQL Server) makes extra cores add licence cost.
- Memory: use ECC RAM for servers. Populate memory channels evenly for best performance. Virtualisation hosts usually need more RAM than CPU.
- Storage controller: hardware RAID controller with cache and battery or flash protection for production servers. Hot-swap bays allow replacing a failed drive without downtime.
- Redundancy: redundant hot-plug power supplies connected to separate circuits or a UPS, redundant fans, and dual network ports.
- Remote management: a baseboard management controller (iLO, iDRAC, IMM/XClarity, IPMI) allows remote console, power control, and hardware alerts without visiting the site.
- Warranty and support: confirm the coverage level, response time (for example next business day or 4-hour on-site), and the in-country service provider. Extended warranties can be quoted at the time of sale.
- Typical environment: servers need cool, dust-free rooms with stable power. Typical operating temperature is about 18 to 27 degrees Celsius.
- Common troubleshooting: server will not boot (check power supplies, memory seating, and the BMC event log); degraded RAID (replace the failed drive and let it rebuild, do not remove other drives); high temperature alarm (check fans, airflow, and room cooling); slow performance (check CPU, memory, disk queue, and network).

## 2. Storage
- DAS (direct-attached storage): disks attached to one server. Simple and fast, but not shared.
- NAS (network-attached storage): file-level sharing over the network (SMB, NFS). Good for file shares, backups, and small business use.
- SAN (storage area network): block-level storage over Fibre Channel or iSCSI for virtualisation clusters and databases.
- Drive types: HDD (lowest cost per terabyte, good for capacity and backup), SATA SSD (faster, mixed workloads), SAS drives (enterprise, dual-port, hot-swap), NVMe SSD (highest performance for databases and virtualisation). Use enterprise or NAS-rated drives in arrays, not desktop drives.
- RAID levels and usable capacity with n identical drives:
  - RAID 0: striping, capacity n, no redundancy (not for important data).
  - RAID 1: mirroring, capacity n/2, survives one drive failure per mirror.
  - RAID 5: capacity n-1, survives one drive failure, needs at least 3 drives. Rebuilds on large drives can be slow and risky.
  - RAID 6: capacity n-2, survives two drive failures, needs at least 4 drives. Recommended for large-capacity HDD arrays.
  - RAID 10: capacity n/2, striped mirrors, needs at least 4 drives, good performance and redundancy.
- RAID is not a backup. A backup must be a separate copy. Follow the 3-2-1 rule: 3 copies of data, on 2 different media, with 1 copy off-site or offline (immutable or air-gapped to resist ransomware).
- Sizing: add the current data, expected growth per year multiplied by the number of years, snapshots or backup retention, and 20 to 30 percent free space headroom.
- Backup design: define RPO (how much data loss is acceptable) and RTO (how long recovery may take). Test restores regularly.

## 3. Printers and Multifunction Devices
- Laser (toner) printers: fast, low cost per page, good for text-heavy offices. Colour laser costs more per page than mono.
- Inkjet and ink-tank printers: lower purchase cost, good for photos and low to medium volume. Ink-tank models have a very low cost per page.
- Multifunction printers (MFP): print, copy, scan, and often fax. Check scan-to-email, scan-to-folder, ADF (automatic document feeder), duplex, and authentication options.
- Selection criteria: monthly page volume and duty cycle (choose a device whose recommended monthly volume is well above your average), print speed in pages per minute, paper sizes (A4, Legal, A3), colour or mono, network connectivity (Ethernet, Wi-Fi), security features such as secure print release, and cost per page.
- Consumables: use original or vendor-approved toner and ink to protect print quality and warranty. Match the cartridge model to the printer model, and check for region-specific cartridges.
- Common troubleshooting: printer offline (check network cable or Wi-Fi, IP address, and the print queue); paper jams (check the correct paper type and weight, clean rollers, remove all torn pieces); streaks or faded print (replace toner or clean the drum and fuser area); slow printing (check driver, large graphics, and network); cannot scan to folder (check SMB version, credentials, firewall, and the shared folder path).
- Security: change default admin passwords, update firmware, and disable unused services. Printers store scanned data, and this may include personal data covered by the Data Privacy Act.

## 4. Plotters and Large-Format Printers
- Use cases: CAD drawings, architectural plans, GIS maps, posters, and signage.
- Paper sizes: A2 (420 x 594 mm), A1 (594 x 841 mm), A0 (841 x 1189 mm). Roll widths are commonly 24 inches (610 mm), 36 inches (914 mm), and 44 inches (1118 mm). A 36-inch plotter handles A0 prints.
- Technology: inkjet plotters with dye ink (vivid colours for posters) or pigment ink (water-resistant, sharp lines for technical drawings). LED/laser large-format devices suit high-volume line drawings.
- Selection criteria: maximum roll width, print speed for A1 or A0, number of inks and colours, ink tank size, media handling (roll, sheet, auto-cutter), network connectivity, file formats supported (PDF, HP-GL/2, TIFF, JPEG), and the optional scanner.
- Consumables: ink cartridges, printheads, maintenance cartridges, paper rolls (bond, coated, photo, film). Always use media on the vendor's supported list.
- Common troubleshooting: banding or missing lines (run printhead cleaning and alignment); ink smudging (use the right media profile and allow drying time); paper skew (reload the roll and check the roll core size); file will not print (use PDF, check the driver).

## 5. UPS (Uninterruptible Power Supply)
- Types:
  - Offline or standby: lowest cost, a short switchover time. Suitable for desktops and small equipment.
  - Line-interactive: regulates voltage with an automatic voltage regulator (AVR) without using the battery. Common for small offices, network equipment, and small servers.
  - Online double-conversion: continuously supplies clean power from the inverter with zero transfer time. Recommended for servers, storage, and sensitive equipment.
- VA versus watts: UPS capacity is rated in VA (volt-amperes) and watts. Real power in watts = VA x power factor. Many older units have a power factor of about 0.6 to 0.7, while newer units are often 0.9 to 1.0. Always size using the watt rating.
- Sizing steps: (1) add the wattage of all equipment connected to the UPS (use the nameplate or the power supply rating, or measured consumption); (2) add 20 to 30 percent headroom for growth and inrush; (3) choose a UPS whose watt rating is above that figure; (4) check the runtime chart for the required backup time at that load.
- Runtime: depends on load and battery capacity. For longer runtime, add external battery packs. For long outages, combine the UPS with a generator and an automatic shutdown plan.
- Software and shutdown: install the vendor's management software or a network management card so servers shut down gracefully before the battery runs out.
- Battery life: sealed lead-acid batteries typically last three to five years, shorter in hot environments. Replace batteries on schedule, and test them periodically.
- Rack and tower: choose rack-mount (1U, 2U, 3U) for racks and tower for floor use. Check plug types and output sockets (C13 and C19) against the equipment.
- Common troubleshooting: UPS beeps continuously (overload or low battery); runtime is short (aged batteries, replace); UPS will not switch on (check the battery connector and the input breaker); "replace battery" indicator (run a self-test and replace).

## 6. Network Switches
- Unmanaged switches: plug-and-play, no configuration. Good for small, simple networks.
- Smart or web-managed switches: basic features such as VLANs, QoS, and port mirroring through a web interface.
- Managed switches: full configuration via CLI or web, with advanced VLANs, link aggregation (LACP), spanning tree, access control lists, monitoring (SNMP), and security (802.1X, port security).
- Layer 2 versus Layer 3: Layer 2 switches forward by MAC address. Layer 3 switches also route between VLANs and subnets at wire speed, and are used in the network core or distribution layer.
- Ports and speed: 1 Gbps (Gigabit) for access ports, 2.5 or 5 Gbps for modern Wi-Fi 6 and Wi-Fi 7 access points, and 10 Gbps (SFP+) uplinks and server connections. Plan uplink capacity so access ports are not oversubscribed.
- SFP and SFP+ slots: take optical or copper transceivers, and the transceiver must match the speed, wavelength, and fibre type (single-mode or multi-mode). Check vendor compatibility.
- PoE (Power over Ethernet): powers IP phones, access points, and cameras over the network cable. Standards: 802.3af (PoE, up to 15.4 W per port), 802.3at (PoE+, up to 30 W), 802.3bt (PoE++, up to 60 W or 90 W). Always check the switch's total PoE budget in watts, which is less than the number of ports multiplied by the per-port maximum.
- Stacking and redundancy: stackable switches act as one unit. Redundant power supplies are available on some models.
- Typical sizing: count the devices, add 20 to 30 percent spare ports, choose uplinks, and decide VLANs for staff, guests, servers, voice, and cameras.
- Common troubleshooting: no link (check cable, port, and speed or duplex mismatch); slow network (check for loops, a broadcast storm, and duplex errors); PoE device not powering (check the PoE budget, the cable length of up to 100 m, and the standard); cannot reach a VLAN (check trunk and tagged VLAN settings).

## 7. Firewalls and Network Security
- Firewall types: traditional stateful firewall; next-generation firewall (NGFW) with application control, intrusion prevention (IPS), and user identity; unified threat management (UTM) which bundles antivirus, web filtering, anti-spam, and VPN.
- Sizing: look at the throughput figure with the security features enabled (threat-protection or NGFW throughput), not only the maximum firewall throughput. The first is often much lower. Also consider the number of concurrent sessions, VPN tunnels and users, the internet bandwidth, and the number of users and devices.
- Licensing: many security features (IPS, antivirus, web filtering, application control, sandboxing, updates) need an active subscription. When the subscription expires, protection may stop, and in some products firmware and signature updates stop. Confirm what the licence includes and the renewal date.
- VPN: site-to-site VPN (IPsec) connects branches. Remote-access VPN (SSL or IPsec client) connects staff working from home. Use multi-factor authentication for remote access.
- High availability (HA): two firewalls in active-passive or active-active mode avoid a single point of failure.
- Best practices: change default passwords, restrict management access, keep firmware current, segment networks (VLANs for guests, servers, and IoT), log and review events, and back up the configuration.
- Related security products: endpoint protection (EDR), email security, backup and ransomware protection, and Wi-Fi access points with WPA3.
- Common troubleshooting: users cannot access a website (check the web filter category and policy); VPN will not connect (check credentials, certificates, the client version, and the firewall policy and port forwarding); slow internet (check throughput limits with security features enabled and the WAN link).

## 8. Operating Systems and Licensing
- Windows client versions: Windows 10 reached end of support on 14 October 2025. Devices should be upgraded to Windows 11 or enrolled in Extended Security Updates where available. Windows 11 minimum requirements include a 64-bit processor (1 GHz or faster, two or more cores), 4 GB RAM, 64 GB storage, UEFI with Secure Boot, TPM 2.0, and a compatible graphics card. Some older PCs do not meet these requirements.
- Windows Server licensing: licensed per physical core (minimum of 8 core licences per processor and 16 per server) plus Client Access Licences (CALs) for users or devices. Standard edition includes rights for two virtual machines, and Datacenter edition allows unlimited virtual machines. Additional Remote Desktop Services (RDS) CALs are needed for remote desktop sessions.
- Licence types: OEM (tied to the device it was first installed on, supplied with new hardware), retail or full-packaged product (transferable), and volume licensing (such as through Microsoft agreements or cloud partner programmes). Subscription options such as Microsoft 365 include Office apps and cloud services.
- Linux and other operating systems: enterprise distributions (for example Red Hat Enterprise Linux, SUSE) require paid subscriptions for support and updates. Open-source distributions are free but support is self-managed or contracted separately.
- Hypervisors and virtualisation: VMware (subscription licensing), Microsoft Hyper-V (included with Windows Server), Proxmox and others. Check the host hardware compatibility list and licensing per CPU or core.
- Software compliance: using unlicensed software exposes customers and the company to legal and security risks. Do not install or sell unlicensed software.

## 9. Laptops, Desktops, Memory and SSD Upgrades
- Compatibility must be checked against the exact model's datasheet or service manual. Do not guess from the processor generation alone.
- Memory (RAM): confirm the type (DDR4, DDR5, LPDDR), form factor (SODIMM for laptops, DIMM for desktops), speed, the number of slots, and the maximum supported capacity. Some laptops have soldered memory that cannot be upgraded.
- Storage: confirm the interface (SATA or NVMe PCIe), the form factor (2.5-inch, M.2 2280, M.2 2242), and whether the slot supports the PCIe generation. A faster drive in a slower slot will run at the slot's limit.
- Warranty note: opening the device or fitting non-approved parts may affect the warranty for some brands. Confirm with the vendor.
- Monitors, docks, and accessories: check ports (HDMI, DisplayPort, USB-C with DisplayPort Alt Mode or Thunderbolt), resolution, refresh rate, and the power delivery wattage for docks.

## 10. Warranty, RMA and After-Sales Support
- Collect before opening a support case: customer name, product model, serial number, purchase invoice or delivery receipt, a clear description of the fault, steps already tried, photos or error codes, and the site address.
- Standard RMA flow: log the case with the vendor or the internal service desk; basic troubleshooting by phone or remote session; if the fault is confirmed, an RMA number is issued; the unit is replaced or repaired according to the warranty terms; keep the RMA reference in the customer record.
- Warranty usually covers manufacturing defects. It typically does not cover physical damage, liquid damage, power surges without protection, unauthorised repair, or consumables such as toner, ink, and batteries (UPS batteries often carry a shorter warranty).
- Before sending any storage device or computer for repair or replacement, ask the customer to back up their data. Personal data on devices must be protected (see the Data Privacy Act guide), and the technician must follow the customer's wipe or retention instructions.
- Exact warranty periods, response times, and replacement terms depend on the vendor and the contract. Always check the product's warranty card or quotation.

## 11. Preparing a Good Quotation (Checklist)
- Confirm the requirement: users, workload, locations, growth plans, and budget.
- Confirm compatibility: operating system, power and cooling, rack space, network speed, and cabling.
- Include licences and subscriptions (OS, CALs, firewall subscriptions, backup software), installation and configuration services, and warranty or support extensions.
- State validity period, lead time, and delivery terms from Sales Operations.
- Follow the discount approval matrix and credit check requirements in the Sales Order workflow before committing.

## 12. Common Employee IT Help Questions
- Forgot password or locked account: use the self-service reset if available, or contact the IT service desk. Never share passwords.
- Cannot connect to company Wi-Fi or VPN: check the network, credentials, and multi-factor authentication. Restart the VPN client. If it persists, open a ticket with IT.
- Suspicious email or link (phishing): do not click or open attachments. Report it to IT Security. If you already clicked or entered credentials, report it immediately because it may be a personal data breach.
- Lost or stolen laptop or phone: report immediately to IT and the Data Protection Officer so the device can be locked or wiped and the breach assessed.
- Software installation: request through IT. Only licensed and approved software is allowed.
