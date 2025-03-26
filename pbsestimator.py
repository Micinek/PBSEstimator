#!/usr/bin/env python3
"""
Proxmox Backup Size Estimator

This script calculates the total referenced backup size for VMs and LXC containers
stored in a Proxmox Backup Server datastore. It provides detailed insights into
backup sizes, including per-snapshot and per-namespace breakdowns.

Usage Examples:
  - Calculate backup sizes for all VMs and CTs in a specific datastore (does not include namespaces):
      ./pbsestimator.py /mnt/datastores/central

  - Show a summary of total space used per VM/CT (no per-snapshot details):
      ./pbsestimator.py -s /mnt/datastores/central

  - Output results in JSON format for automation or further processing:
      ./pbsestimator.py -j /mnt/datastores/central

  - Calculate backup sizes for a specific namespace:
      ./pbsestimator.py -n mynamespace /mnt/datastores/central

  - Calculate backup sizes for all namespaces within a datastore:
      ./pbsestimator.py --all-namespaces /mnt/datastores/central

  - Enable verbose mode for detailed processing logs:
      ./pbsestimator.py -v /mnt/datastores/central

  - Filter backups by specific VM/CT IDs (single ID, range, or comma-separated list):
      ./pbsestimator.py -i 100,101-105 /mnt/datastores/central

  - Include snapshots with no new chunks in the calculation:
      ./pbsestimator.py -a /mnt/datastores/central

  - Sort output by highest space usage (blame mode):
      ./pbsestimator.py -b /mnt/datastores/central

  - Save results to a file:
      ./pbsestimator.py -o output.txt /mnt/datastores/central

Options:
  -i,  --id            Filter by VM/LXC IDs (single ID, range, or comma-separated values).
  -v,  --verbose       Enable verbose output for detailed processing logs.
  -j,  --json          Output results in JSON format for automation or further processing.
  -a,  --all           Include snapshots with no new chunks in the calculation.
  -s,  --sum           Show only the total referenced sizes for each VM/CT (no per-snapshot details).
  -b,  --blame         Sort output by highest space usage (blame mode).
  -n,  --namespace     Specify a namespace to scan (default: root namespace).
  -an, --all-namespaces    Scan all namespaces within the datastore.
  -o,  --output        Save results to a file.
  datastore           Path to the Proxmox Backup Server datastore (e.g., /mnt/datastores/central).
"""

import os
import sys
import argparse
import json
import operator

def argparser():
    parser = argparse.ArgumentParser(
        description="Estimate space used by VMs and LXC containers in a Proxmox Backup Server datastore.",
        formatter_class=argparse.RawTextHelpFormatter  # Preserves formatting in help text
    )
    parser.add_argument(
        "-i", "--id", metavar="vmids", dest="vmids", type=str,
        help="Filter by VM/LXC IDs (single ID, range, or comma-separated values).\n"
             "Example: -i 100,101-105"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose output for detailed processing logs."
    )
    parser.add_argument(
        "-j", "--json", action="store_true",
        help="Output results in JSON format for automation or further processing."
    )
    parser.add_argument(
        "-a", "--all", action="store_true",
        help="Include snapshots with no new chunks in the calculation."
    )
    parser.add_argument(
        "-s", "--sum", action="store_true",
        help="Show only the total referenced sizes for each VM/CT (no per-snapshot details)."
    )
    parser.add_argument(
        "-b", "--blame", action="store_true",
        help="Sort output by highest space usage (blame mode)."
    )
    parser.add_argument(
        "-n", "--namespace", metavar="namespace", type=str,
        help="Specify a namespace to scan (default: root namespace).\n"
             "Example: -n mynamespace"
    )
    parser.add_argument(
        "-an", "--all-namespaces", action="store_true",
        help="Scan all namespaces within the datastore."
    )
    parser.add_argument(
        "-o", "--output", metavar="output_file", type=str,
        help="Save results to a file.\n"
             "Example: -o output.txt"
    )
    parser.add_argument(
        "datastore", metavar="datastore", type=str,
        help="Path to the Proxmox Backup Server datastore.\n"
             "Example: /mnt/datastores/central"
    )
    return vars(parser.parse_args())

def get_datastore_path(datastore, namespace=None):
    path = os.path.join("/mnt/datastore", datastore) if not os.path.isabs(datastore) else datastore
    if namespace:
        path = os.path.join(path, "ns", namespace)
    return path

def check_existing_ids(datastore_path):
    vm_ct_list = []
    for category in ["vm", "ct"]:
        category_path = os.path.join(datastore_path, category)
        if os.path.isdir(category_path):
            for vmid in os.listdir(category_path):
                if os.path.isdir(os.path.join(category_path, vmid)):
                    vm_ct_list.append((category, int(vmid)))
    return vm_ct_list

def get_absolute_paths(vm_ct_list, datastore_path):
    file_list = []
    for category, vmid in vm_ct_list:
        scan_path = os.path.join(datastore_path, category, str(vmid))
        if os.path.isdir(scan_path):
            files = [
                os.path.join(root, f)
                for root, _, filenames in os.walk(scan_path)
                for f in filenames
                if (f.endswith(".img.fidx") and category == "vm") or (f.endswith("root.pxar.fidx") or f.endswith("root.pxar.didx") and category == "ct")
            ]
            if files:
                file_list.append({"category": category, "vmid": vmid, "files": files})
    return file_list

def count_blocks(vm_list):
    total_namespace_bytes = 0
    snapshots = []
    for vm in vm_list:
        chunk_set = set()
        vm_snapshots = []
        total_bytes = 0
        for filepath in vm["files"]:
            with open(filepath, "rb") as f:
                f.seek(4096)
                data = f.read().hex()
                new_chunks = {data[i:i+64] for i in range(0, len(data), 64) if data[i:i+64] not in chunk_set}
                chunk_set.update(new_chunks)
                snapshot_size = len(new_chunks) * 4194304
                vm_snapshots.append({
                    "snapshot": os.path.basename(os.path.dirname(filepath)),
                    "new_chunks": len(new_chunks),
                    "new_chunks_bytes": snapshot_size,
                })
                total_bytes += snapshot_size
        total_namespace_bytes += total_bytes
        snapshots.append({
            "category": vm["category"],
            "vmid": vm["vmid"],
            "snapshots": vm_snapshots,
            "total_bytes": total_bytes,
        })
    return snapshots, total_namespace_bytes

def list_namespaces(datastore_path):
    namespaces = []
    ns_path = os.path.join(datastore_path, "ns")
    if os.path.isdir(ns_path):
        namespaces = [name for name in os.listdir(ns_path) if os.path.isdir(os.path.join(ns_path, name))]
    return namespaces

def write_output(output_file, content):
    with open(output_file, "w") as f:
        f.write(content)

if __name__ == "__main__":
    args = argparser()
    datastore_path = get_datastore_path(args["datastore"], args["namespace"])

    if args["all_namespaces"]:
        namespaces = list_namespaces(datastore_path)
        output_content = ""
        for namespace in namespaces:
            namespace_path = get_datastore_path(args["datastore"], namespace)
            existing_ids = check_existing_ids(namespace_path)
            vm_ct_paths = get_absolute_paths(existing_ids, namespace_path)
            results, total_namespace_bytes = count_blocks(vm_ct_paths)
            namespace_output = f"Namespace {namespace}: {total_namespace_bytes / (1024**3):.2f} GiB\n"
            output_content += namespace_output
            print(namespace_output)
        if args["output"]:
            write_output(args["output"], output_content)
    else:
        existing_ids = check_existing_ids(datastore_path)
        vm_ct_paths = get_absolute_paths(existing_ids, datastore_path)
        results, total_namespace_bytes = count_blocks(vm_ct_paths)

        # Blame mode: Sort by highest space usage
        if args["blame"]:
            results.sort(key=lambda x: x["total_bytes"], reverse=True)

        # JSON output
        if args["json"]:
            print(json.dumps(results, indent=4))
            if args["output"]:
                write_output(args["output"], json.dumps(results, indent=4))
            sys.exit(0)

        output_content = ""
        if args["sum"]:
            for item in results:
                item_output = f"{item['category'].upper()} ID: {item['vmid']}\n"
                item_output += f"Total referenced size: {item['total_bytes'] / (1024**3):.2f} GiB\n"
                item_output += "-" * 40 + "\n"
                output_content += item_output
                print(item_output)
            total_output = f"Total Namespace Size: {total_namespace_bytes / (1024**3):.2f} GiB\n"
            output_content += total_output
            print(total_output)
        else:
            for item in results:
                item_output = f"{item['category'].upper()} ID: {item['vmid']}\n"
                item_output += f"Total referenced size: {item['total_bytes'] / (1024**3):.2f} GiB\n"
                for snap in item["snapshots"]:
                    item_output += f" - {snap['snapshot']}: {snap['new_chunks']} chunks ({snap['new_chunks_bytes'] / (1024**3):.2f} GiB)\n"
                item_output += "-" * 40 + "\n"
                output_content += item_output
                print(item_output)
            total_output = f"Total Namespace Size: {total_namespace_bytes / (1024**3):.2f} GiB\n"
            output_content += total_output
            print(total_output)

        if args["output"]:
            write_output(args["output"], output_content)
