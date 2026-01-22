"""
Monitor script to manage virtual machines in the sandbox
To run this script directly, use the following command:
`python -m utils.monitor` from the sandbox directory
"""

import asyncio
import platform
import logging
import subprocess
import sqlalchemy

# set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def vmware_linux_reset_snapshot(name, snapshot):
    """Reset VM to snapshot for VMware on Linux
    
    Args:
    - name (str): name of VM (e.g. full path to .vmx file)
    - snapshot (str): name of snapshot to reset to

    Returns:
    - None
    """

    p = subprocess.Popen(['vmrun', '-T', 'ws', 'revertToSnapShot', name, snapshot], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    if p.returncode != 0:
        logging.error(f"Error resetting snapshot {name} - {snapshot}")
        out = out.decode("utf-8")
        err = err.decode("utf-8")
        logging.error(out)
        logging.error(err)
        return False

    # wait for VM to reset
    running_vms = vmware_linux_get_running_vms()
    while name in running_vms:
        logging.debug(f"Waiting for VM {name} to reset")
        await asyncio.sleep(1)
        running_vms = vmware_linux_get_running_vms()

    # start the VM
    vmware_linux_start_vm(name)

    logging.info(f"Reset snapshot {name} - {snapshot}")
    return True

async def vmware_linux_start_vm(name):
    """Start VM for VMware on Linux
    
    Args:
    - name (str): name of VM (e.g. full path to .vmx file)

    Returns:
    - None
    """
    
    p = subprocess.Popen(['vmrun', '-T', 'ws', 'start', name, 'nogui'])

    # wait for VM to start
    running_vms = vmware_linux_get_running_vms()
    while name not in running_vms:
        logging.debug(f"Waiting for VM {name} to start")
        await asyncio.sleep(1)
        running_vms = vmware_linux_get_running_vms()

    logging.info(f"Started VM {name}")

def vmware_linux_get_running_vms():
    """Get running VMs for VMware on Linux
    
    Args:
    - None

    Returns:
    - vms (list): list of running VMs
    """

    p = subprocess.Popen(['vmrun', '-T', 'ws', 'list'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    if p.returncode != 0:
        logging.error(f"Error getting running VMs")
        out = out.decode("utf-8")
        err = err.decode("utf-8")
        logging.error(out)
        logging.error(err)
        return None
    
    vms = out.decode("utf-8").split('\n')[1:]
    vms = [vm.strip() for vm in vms if vm.strip() != '']
    # logging.debug(f"Running VMs: {vms}")

    return vms

async def virsh_reset_snapshot(name, snapshot):
    """Reset VM to snapshot using virsh (libvirt) locally on Linux
    
    Args:
    - name (str): name of VM 
    - snapshot (str): name of snapshot to reset to

    Returns:
    - None
    """
    logging.info(f"Resetting snapshot {name} - {snapshot}...")
    p = subprocess.Popen(['virsh', 'snapshot-revert', name, snapshot], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    if p.returncode != 0:
        logging.error(f"Error resetting snapshot {name} - {snapshot}")
        out = out.decode("utf-8")
        err = err.decode("utf-8")
        logging.error(out)
        logging.error(err)
        return False
    
    logging.info(f"Reset snapshot {name} - {snapshot}")
    return True

def virsh_get_running_vms():
    """Get running VMs for virsh (libvirt) on Linux
    
    Args:
    - None

    Returns:
    - vms (list): list of running VMs
    """

    p = subprocess.Popen(['virsh', 'list', '--state-running', '--name'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    if p.returncode != 0:
        logging.error(f"Error getting running VMs")
        out = out.decode("utf-8")
        err = err.decode("utf-8")
        logging.error(out)
        logging.error(err)
        return None
    
    vms = out.decode("utf-8").strip().split('\n')
    vms = [vm.strip() for vm in vms if vm.strip() != '']
    # logging.debug(f"Running VMs: {vms}")

    return vms

async def virsh_start_vm(name):
    """Start VM for virsh (libvirt) on Linux
    
    Args:
    - name (str): name of VM

    Returns:
    - None
    """
    
    p = subprocess.Popen(['virsh', 'start', name])

    # wait for VM to start
    running_vms = virsh_get_running_vms()
    while name not in running_vms:
        logging.debug(f"Waiting for VM {name} to start")
        await asyncio.sleep(1)
        running_vms = virsh_get_running_vms()

    logging.info(f"Started VM {name}")

async def main():
    """
    Main function to monitor VMs while running independent of the Flask app
    """
    import sys
    import os
    
    # Add parent directory to path for imports
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from models import Analysis
    from config import Config
    
    config = Config() 


    # check host OS
    host_os = platform.system()

    if host_os != 'Linux':
        print("Host OS is not supported: {}".format(host_os))
        return

    # read config file for VM provider
    vm_provider = config.VM_PROVIDER.strip().lower()

    if vm_provider == 'vmware':
        reset_snapshot = vmware_linux_reset_snapshot
        start_vm = vmware_linux_start_vm
        get_running_vms = vmware_linux_get_running_vms
    elif vm_provider == 'libvirt':
        reset_snapshot = virsh_reset_snapshot
        start_vm = virsh_start_vm
        get_running_vms = virsh_get_running_vms
    else:
        print("Unknown VM provider: {}".format(vm_provider))

    # get VMs from config
    vms = config.VMS

    # initialize VMs by resetting to snapshot
    list_of_tasks = [reset_snapshot(vm['name'], vm['snapshot']) for vm in vms]
    await asyncio.gather(*list_of_tasks)

    # # wait until VMs are ready
    # running_vms = get_running_vms()
    # while len(running_vms) > 0:
    #     await asyncio.sleep(1)
    #     running_vms = get_running_vms()

    # start VMs
    list_of_tasks = [start_vm(vm['name']) for vm in vms]
    await asyncio.gather(*list_of_tasks)

    # set up database connection
    engine = sqlalchemy.create_engine(config.SQLALCHEMY_DATABASE_URI)
    Session = sqlalchemy.orm.sessionmaker(bind=engine)
    session = Session()
    
    # loop to monitor VMs
    while True:
        try:
            # Clear session cache to get fresh data
            session.expire_all()
            
            # get all analyses currently running
            analyses = session.query(Analysis).filter(Analysis.status == 1).all()

            # check if time since the date_updated time of the analysis is greater than the timeout time
            for analysis in analyses:
                session.commit() # commit to refresh date_updated
                # make sure status has not changed
                session.refresh(analysis)
                if analysis.status != 1:
                    continue
                current_time = session.query(sqlalchemy.func.current_timestamp()).scalar()
                current_time = current_time.replace(tzinfo=None)
                last_updated = analysis.date_updated.replace(tzinfo=None)
                time_diff = (current_time - last_updated).total_seconds()
                # check if time difference is greater than timeout
                logging.debug(f"Analysis: {analysis.id} Current time: {current_time}, last updated: {last_updated}, time difference: {time_diff}")
                if time_diff > config.VM_TIMEOUT:
                    # set status to 3 (error)
                    analysis.status = 3
                    analysis.error_message = "analysis VM timeout"
                    session.add(analysis)
                    session.commit()
                    
                    # reset VM to snapshot
                    # find snapshot name
                    snapshot = None
                    for vm in vms:
                        if vm['name'] == analysis.analysis_vm:
                            snapshot = vm['snapshot']
                            break
                    if snapshot is None:
                        logging.error(f"Could not find snapshot for VM {analysis.analysis_vm}")
                        continue
                    await reset_snapshot(analysis.analysis_vm, snapshot)
                    
                    # wait until VM is ready
                    running_vms = get_running_vms()
                    while analysis.analysis_vm not in running_vms:
                        logging.debug(f"Waiting for VM {analysis.analysis_vm} to reset")
                        await asyncio.sleep(1)
                        running_vms = get_running_vms()

                    # # start VM
                    # await start_vm(analysis.analysis_vm)

                    # log
                    logging.info(f"Reset VM {analysis.analysis_vm} for analysis {analysis.id} due to timeout")

        except Exception as e:
            logging.error(f"Error in monitor loop: {e}")

        # sleep for 10 seconds
        await asyncio.sleep(10)    

if __name__ == '__main__':
    asyncio.run(main())