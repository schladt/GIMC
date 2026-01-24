"""
Utility function to forcibly shut down all VMs
"""

import sys
import logging
import asyncio
import os
import subprocess

# set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def libvirt_shutdown_vm(vm):
    p = subprocess.Popen(['virsh', 'destroy', vm], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    if p.returncode != 0:
        logging.error(f"Error resetting snapshot {vm}")
        out = out.decode("utf-8")
        err = err.decode("utf-8")
        logging.error(out)
        logging.error(err)
        return False
    
    logging.info(f"Shut down VM {vm}")
    return True

async def main():
    from ..config import Config

    config = Config()

    # check if vm manager is libvirt
    if config.VM_PROVIDER.strip().lower() == 'libvirt':
        shutdown_vm = libvirt_shutdown_vm
    else:
        logging.error("VM provider not supported")
        return

    # get VMs from config
    vms = config.VMS

    # shut down VMs via gather
    tasks = []
    for vm in vms:
        tasks.append(shutdown_vm(vm['name']))
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())