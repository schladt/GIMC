#!/usr/bin/env bash
# kvm_ext_snapshot.sh
#
# Create a live *external* snapshot (RAM + disk overlays) for a libvirt/KVM VM.
# Files go under: /var/lib/libvirt/snapshots/<vm>/<snapshot>/
#
# Usage:
#   sudo ./kvm_ext_snapshot.sh <vm-name> <snapshot-name>
#
# Snapshot command cheetsheet:
#   List:    sudo virsh snapshot-list <vm-name>
#   Restore: sudo virsh snapshot-revert <vm-name> <snapshot-name>
#   Delete:  sudo virsh snapshot-delete --metadata <vm-name> <snapshot-name>
#            sudo rm -rf /var/lib/libvirt/snapshots/<vm-name>/<snapshot-name>

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <vm-name> <snapshot-name>"
  exit 1
fi

DOMAIN="$1"
SNAPNAME="$2"

# Where to store snapshots
SNAP_ROOT="/var/lib/libvirt/snapshots"
BASE="${SNAP_ROOT}/${DOMAIN}/${SNAPNAME}"

if [[ -e "$BASE" ]]; then
  echo "Error: snapshot directory already exists: $BASE"
  exit 1
fi

mkdir -p "$BASE"

echo "Creating external snapshot for domain '$DOMAIN' named '$SNAPNAME'"
echo "Snapshot files will be stored under: $BASE"
echo

# Make sure the domain exists
if ! virsh dominfo "$DOMAIN" >/dev/null 2>&1; then
  echo "Error: domain '$DOMAIN' not found."
  exit 1
fi

# Collect --diskspec args for all non-ISO block devices
diskspec_args=()

# Skip header lines and only process real rows
# Format: Target  Source
while read -r target source; do
  # Skip header / separator
  [[ "$target" == "Target" ]] && continue
  [[ "$target" == "-------" ]] && continue
  [[ -z "$target" ]] && continue

  # Skip entries without a real source
  [[ -z "${source:-}" || "$source" == "-" ]] && continue

  # Skip obvious ISO/cdrom images
  if [[ "$source" == *.iso ]]; then
    continue
  fi

  disk_snap_path="${BASE}/${target}.qcow2"
  echo "  Will snapshot disk: target=${target}, base=${source}, overlay=${disk_snap_path}"
  diskspec_args+=( --diskspec "${target},snapshot=external,file=${disk_snap_path}" )

done < <(virsh domblklist "$DOMAIN" | awk 'NR>2 && NF>=2 {print $1, $2}')

if [[ ${#diskspec_args[@]} -eq 0 ]]; then
  echo "Error: no suitable disks found to snapshot."
  exit 1
fi

memfile="${BASE}/mem"
memspec="snapshot=external,file=${memfile}"

echo
echo "Memory snapshot file: ${memfile}"
echo

# Take the live external snapshot (RAM + disks)
virsh snapshot-create-as \
  --domain "$DOMAIN" \
  --name "$SNAPNAME" \
  --description "External snapshot '$SNAPNAME' for '$DOMAIN'" \
  --live \
  --memspec "$memspec" \
  "${diskspec_args[@]}" \
  --atomic

echo
echo "Snapshot '$SNAPNAME' for domain '$DOMAIN' created successfully."
echo "Files are under: $BASE"
