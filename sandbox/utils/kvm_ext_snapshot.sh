#!/usr/bin/env bash
# kvm_ext_snapshot.sh
#
# Manage live *external* snapshots (RAM + disk overlays) for libvirt/KVM VMs.
# Files go under: /var/lib/libvirt/snapshots/<vm>/<snapshot>/
#
# Usage:
#   sudo ./kvm_ext_snapshot.sh --create <vm-name> <snapshot-name>
#   sudo ./kvm_ext_snapshot.sh --list <vm-name>
#   sudo ./kvm_ext_snapshot.sh --restore <vm-name> <snapshot-name>
#   sudo ./kvm_ext_snapshot.sh --delete <vm-name> <snapshot-name>

set -euo pipefail

# Where to store snapshots
SNAP_ROOT="/var/lib/libvirt/snapshots"

show_usage() {
  cat << EOF
Usage: $0 [OPERATION] <vm-name> [snapshot-name]

Operations:
  --create <vm-name> <snapshot-name>    Create a new external snapshot
  --list <vm-name>                      List all snapshots for a VM
  --restore <vm-name> <snapshot-name>   Restore VM to a snapshot
  --delete <vm-name> <snapshot-name>    Delete a snapshot

Default operation (no flag): --create
EOF
  exit 1
}

list_snapshots() {
  local domain="$1"
  echo "Snapshots for domain '$domain':"
  virsh snapshot-list "$domain"
}

restore_snapshot() {
  local domain="$1"
  local snapname="$2"
  echo "Restoring domain '$domain' to snapshot '$snapname'..."
  virsh snapshot-revert "$domain" "$snapname"
  echo "Snapshot restored successfully."
}

delete_snapshot() {
  local domain="$1"
  local snapname="$2"
  local snap_dir="${SNAP_ROOT}/${domain}/${snapname}"
  
  echo "Deleting snapshot '$snapname' for domain '$domain'..."
  
  # Delete metadata from libvirt
  virsh snapshot-delete --metadata "$domain" "$snapname"
  
  # Delete snapshot files if they exist
  if [[ -d "$snap_dir" ]]; then
    echo "Removing snapshot files: $snap_dir"
    rm -rf "$snap_dir"
  fi
  
  echo "Snapshot deleted successfully."
}

# Parse operation
OPERATION="create"
if [[ $# -gt 0 ]] && [[ "$1" == --* ]]; then
  case "$1" in
    --create)
      OPERATION="create"
      shift
      ;;
    --list)
      OPERATION="list"
      shift
      ;;
    --restore)
      OPERATION="restore"
      shift
      ;;
    --delete)
      OPERATION="delete"
      shift
      ;;
    *)
      echo "Error: Unknown operation '$1'"
      show_usage
      ;;
  esac
fi

# Validate arguments based on operation
case "$OPERATION" in
  list)
    if [[ $# -ne 1 ]]; then
      echo "Error: --list requires <vm-name>"
      show_usage
    fi
    DOMAIN="$1"
    list_snapshots "$DOMAIN"
    exit 0
    ;;
  restore)
    if [[ $# -ne 2 ]]; then
      echo "Error: --restore requires <vm-name> <snapshot-name>"
      show_usage
    fi
    DOMAIN="$1"
    SNAPNAME="$2"
    restore_snapshot "$DOMAIN" "$SNAPNAME"
    exit 0
    ;;
  delete)
    if [[ $# -ne 2 ]]; then
      echo "Error: --delete requires <vm-name> <snapshot-name>"
      show_usage
    fi
    DOMAIN="$1"
    SNAPNAME="$2"
    delete_snapshot "$DOMAIN" "$SNAPNAME"
    exit 0
    ;;
  create)
    if [[ $# -ne 2 ]]; then
      echo "Error: --create requires <vm-name> <snapshot-name>"
      show_usage
    fi
    DOMAIN="$1"
    SNAPNAME="$2"
    ;;
esac

# Create snapshot (only for --create operation)
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
