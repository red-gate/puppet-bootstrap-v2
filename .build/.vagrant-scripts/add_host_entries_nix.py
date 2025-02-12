#!/usr/bin/env python3
import json
import os


def main():
    # Hosts file location on Linux
    hosts_file = "/etc/hosts"

    # Import the list of host entries to add
    try:
        with open(
            "/vagrant/.vagrant-scripts/host_entries.jsonc", "r"
        ) as file:
            # The file contains comments which are not valid JSON, so we need to strip them out
            hosts_config = json.loads("".join(line for line in file if not line.strip().startswith("//")))
        if not hosts_config:
            raise ValueError("Failed to import host entries from host_entries.jsonc")
    except Exception as e:
        raise Exception(
            f"Failed to import host entries from host_entries.jsonc.\n{str(e)}"
        )

    # Get the current contents of the hosts file
    try:
        with open(hosts_file, "r") as file:
            current_hosts_content = file.readlines()
    except Exception as e:
        raise Exception(f"Failed to get current contents of {hosts_file}.\n{str(e)}")

    # Convert the current hosts file content to a series of objects
    # (we're only matching IPv4 addresses for simplicity)
    current_hosts = []
    for line in current_hosts_content:
        if line.strip() and not line.startswith("#"):
            parts = line.split()
            if len(parts) >= 2:
                ip, hostname = parts[0], parts[1]
                current_hosts.append({"ip": ip, "hostname": hostname})

    try:
        print(f"Adding host entries to {hosts_file}")
        for entry in hosts_config:
            hostname = entry.get("hostname")
            ip_address = entry.get("ip")
            if not hostname or not ip_address:
                raise ValueError(f"Invalid host entry: {entry}")
            hosts_entry = f"{ip_address} {hostname}"

            # Check if the host entry already exists
            if any(host["hostname"] == hostname for host in current_hosts):
                print(f"Host entry already exists: {hosts_entry}")
            else:
                print(f"Adding host entry: {hosts_entry}")
                with open(hosts_file, "a") as file:
                    file.write(f"{hosts_entry}\n")
    except Exception as e:
        raise Exception(f"Failed to add host entries to {hosts_file}.\n{str(e)}")

    print("Host entries added successfully")


if __name__ == "__main__":
    main()
