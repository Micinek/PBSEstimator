# Proxmox Backup Size Estimator

This Python script calculates the estimated storage usage of VMs (Virtual Machines) and LXC (Linux Containers) on a Proxmox Backup Server (PBS) datastore. It provides insights into the backup sizes by counting the chunks referenced by each backup and estimating the storage consumption based on a fixed chunk size of 4 MiB. The script deduplicates chunks within a single VM/CT backup but does not account for deduplication between different VMs or containers.

## Features

- **Chunk-Based Estimation**: Estimates storage usage by counting unique chunks referenced by backups, assuming a fixed chunk size of 4 MiB.
- **Per-Snapshot Breakdown**: View the size of each snapshot for a VM or container.
- **Per-Namespace Breakdown**: Calculate backup sizes for specific namespaces or all namespaces within a datastore. NOW ALSO SUPPORTS multiple layers of namespaces.
- **Filter by VM/CT IDs**: Filter results by specific VM or container IDs.
- **JSON Output**: Output results in JSON format for automation or further processing.
- **Summary Mode**: Display only the total referenced sizes for each VM/CT without per-snapshot details.
- **Blame Mode**: Sort output by highest space usage to identify the largest consumers.
- **Verbose Mode**: Enable detailed processing logs for debugging.
- **Save Results**: Save the output to a file for later analysis.

## How It Works

The script works by scanning the Proxmox Backup Server datastore and identifying the chunks referenced by each backup. It assumes that each chunk is **4 MiB** in size, which is the default chunk size used by Proxmox Backup Server. The script deduplicates chunks within a single VM/CT backup, meaning it only counts unique chunks for each backup. However, it **does not account for deduplication between different VMs or containers**, so the total estimated size may be higher than the actual storage usage if deduplication is significant across backups.

### Key Notes:
- **Chunk Size Assumption**: The script assumes a fixed chunk size of 4 MiB, which is the default in Proxmox Backup Server. If your setup uses a different chunk size, the estimates may not be accurate.
- **Deduplication**: The script deduplicates chunks **within a single VM/CT backup** but does not account for deduplication **between different VMs or containers**.
- **Estimation**: The results are an **estimate** and may not reflect the exact storage usage, especially in environments with significant cross-VM deduplication.

## Adjusting output for Deduplication in PBS

The script's total referenced size does not account for chunk deduplication across the entire Proxmox Backup Server (PBS). To estimate the realistic size of each namespace in the dataset, you can calculate the deduplication ratio and adjust the per-namespace contributions accordingly.
To **adjust per-namespace contributions based on the deduplication ratio**, we need to **calculate the deduplication factor** and **apply it to each namespace's estimated size**.
> This may be implemented in later date right into the script itself
---

## Step 1: Calculate Deduplication Ratio

The **deduplication ratio** can be determined using:

$$
\text{Deduplication Ratio} = \frac{\text{Sum of All Namespace Referenced Sizes}}{\text{Actual Used Size of Datastore}}
$$

Where:
- **Sum of All Namespace Referenced Sizes** → The total size when each namespace is counted separately.
- **Actual Used Size of Datastore** → The real space used on disk (`90.3492037` TiB in this case).

### Example Calculation:

$$
\text{Deduplication Ratio} = \frac{149.642471}{90.3492037} \approx 1.656
$$

---

## Step 2: Adjust Each Namespace's Contribution

To find the **deduplicated contribution** of each namespace, we **scale down** the referenced size using the deduplication ratio:

$$
\text{Adjusted Namespace Size} = \frac{\text{Namespace Referenced Size}}{\text{Deduplication Ratio}}
$$

### Example:

If a namespace has a referenced size of **25 TiB**:

$$
\text{Adjusted Namespace Size} = \frac{25}{1.656} \approx 15.1 \text{ TiB}
$$

---

## Step 3: Verify the Adjusted Total

Once we scale all namespaces' sizes using the deduplication ratio, the new total should match the actual used space:

$$
\sum \text{Adjusted Namespace Sizes} \approx \text{Actual Used Size of Datastore}
$$

### Example:

$$
\sum \text{Adjusted Namespace Sizes} = 90.3492037 \text{ TiB} \quad (\text{which matches the real PBS usage})
$$

## Usage

To calculate backup sizes for all VMs and containers in a specific datastore (does not include namespaces):

```bash
./pbsestimator.py /mnt/datastores/central
```

### Show Summary

To display only the total referenced sizes for each VM/CT (no per-snapshot details):

```bash
./pbsestimator.py -s /mnt/datastores/central
```

### JSON Output

To output results in JSON format for automation or further processing:

```bash
./pbsestimator.py -j /mnt/datastores/central
```

### Filter by Namespace

To calculate backup sizes for a specific namespace:

```bash
./pbsestimator.py -n mynamespace /mnt/datastores/central
```
**NOW ALSO SUPPORTS multiple layers of namespaces.**

```bash
./pbsestimator.py -n mynamespace/anothernamespace /mnt/datastores/central
```

### Scan All Namespaces

To calculate backup sizes for all namespaces within a datastore:
NOW ALSO SUPPORTS multiple layers of namespaces.

```bash
./pbsestimator.py --all-namespaces /mnt/datastores/central
```

### Verbose Mode

To enable verbose mode for detailed processing logs:

```bash
./pbsestimator.py -v /mnt/datastores/central
```

### Filter by VM/CT IDs

To filter backups by specific VM/CT IDs (single ID, range, or comma-separated list, does not include namespaces):

```bash
./pbsestimator.py -i 100,101-105 /mnt/datastores/central
```

To filter backups by specific namespace and specific VM/CT IDs (single ID, range, or comma-separated list):

```bash
./pbsestimator.py -i -n namespace 100,101-105 /mnt/datastores/central
```


### Include All Snapshots

To include snapshots with no new chunks in the calculation:

```bash
./pbsestimator.py -a /mnt/datastores/central
```

### Blame Mode

To sort output by highest space usage (blame mode):

```bash
./pbsestimator.py -b /mnt/datastores/central
```

### Save Results to a File

To save results to a file:

```bash
./pbsestimator.py -o output.txt /mnt/datastores/central
```

## Options

| Option               | Description                                                                 |
|----------------------|-----------------------------------------------------------------------------|
| `-i, --id`           | Filter by VM/LXC IDs (single ID, range, or comma-separated values).         |
| `-v, --verbose`      | Enable verbose output for detailed processing logs.                         |
| `-j, --json`         | Output results in JSON format for automation or further processing.         |
| `-a, --all`          | Include snapshots with no new chunks in the calculation.                    |
| `-s, --sum`          | Show only the total referenced sizes for each VM/CT (no per-snapshot details). |
| `-b, --blame`        | Sort output by highest space usage (blame mode).                            |
| `-n, --namespace`    | Specify a namespace to scan (default: root namespace).                      |
| `--all-namespaces`   | Scan all namespaces within the datastore.                                   |
| `-o, --output`       | Save results to a file.                                                     |
| `datastore`          | Path to the Proxmox Backup Server datastore (e.g., `/mnt/datastores/central`). |

## Credits

This script is based on the initial work by **masgo** from the [Proxmox Forum post](https://forum.proxmox.com/threads/how-to-get-the-exactly-backup-size-in-proxmox-backup.93901/). It was further enhanced by **BerndHanisch** and **IamLunchbox**:

- [BerndHanisch's GitHub](https://github.com/BerndHanisch/pve/)
- [IamLunchbox's Gist](https://gist.github.com/IamLunchbox/9002b1feb2ca501856b5661c3fe84315)

## License

This script is open-source and available under the MIT License. Feel free to modify and distribute it as needed.

## Contributing

Contributions are welcome! If you have any improvements or bug fixes, please open an issue or submit a pull request.

## Disclaimer

This script is provided as-is, without any warranties. Use it at your own risk. Always test in a safe environment before using in production.
