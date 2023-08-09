"""
Monitor script to manage virtual machines in the sandbox
"""

from config import Config
import platform

# global config
config = Config()


def vmware_linux_reset_snapshot():
    """
    Reset VM to snapshot for VMware on Linux
    """

    # get VMs from config
    print("vmware_linux_reset_snapshot")

def vmware_linux_start_vm():
    """
    Start VM for VMware on Linux
    """

    # get VMs from config
    print("vmware_linux_start_vm")

def main():
    """
    Main function
    """

    # check host OS
    host_os = platform.system()

    if host_os != 'Linux':
        print("Host OS is not supported: {}".format(host_os))
        return

    # read config file for VM provider
    vm_provider = config.VM_PROVIDER

    if vm_provider == 'vmware':
        reset_snapshot = vmware_linux_reset_snapshot
        start_vm = vmware_linux_start_vm

    else:
        print("Unknown VM provider: {}".format(vm_provider))


    reset_snapshot()
    start_vm()

if __name__ == '__main__':
    main()