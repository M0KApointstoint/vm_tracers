# Lima VM configurations

Configuration files for creating Linux virtual machines with
[Lima](https://lima-vm.io).

## ubuntu-vm.yaml

A plain Ubuntu 24.04 LTS virtual machine.

| Resource | Limit  | Notes                                                    |
|----------|--------|----------------------------------------------------------|
| Memory   | 4 GiB  | Used on demand, never more than the limit                |
| Disk     | 60 GiB | Takes about 2 GiB on the host at first, grows on demand  |

### Requirements

- Lima 2.0 or newer ([installation guide](https://lima-vm.io/docs/installation/))
- QEMU, when running on a Linux host

On Ubuntu, QEMU and the UEFI firmware it needs can be installed with:

```bash
sudo apt install qemu-system-x86 qemu-utils ovmf
```

### Usage

Create and start the VM (the first start downloads the Ubuntu image):

```bash
limactl start --name=ubuntu-vm ./ubuntu-vm.yaml
```

Open a shell inside it, or run a single command:

```bash
limactl shell ubuntu-vm
limactl shell ubuntu-vm uname -a
```

Stop it (the disk is kept), or remove it completely:

```bash
limactl stop ubuntu-vm
limactl delete ubuntu-vm
```

### Troubleshooting

`could not find firmware for x86_64`: the UEFI firmware is missing.
On Ubuntu, install the `ovmf` package.

