"""
Monitor script to manage virtual machines in the sandbox
To run this script directly, use the following command:
`python -m utils.monitor` from the sandbox directory
"""

import platform
import logging
import subprocess
import sqlalchemy
import time

# set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def vmware_linux_reset_snapshot(name, snapshot):
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
        return
    
    logging.info(f"Reset snapshot {name} - {snapshot}")

def vmware_linux_start_vm(name):
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
        time.sleep(1)
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
        return
    
    vms = out.decode("utf-8").split('\n')[1:]
    vms = [vm.strip() for vm in vms if vm.strip() != '']
    logging.debug(f"Running VMs: {vms}")

    return vms

def main():
    """
    Main function to monitor VMs while running independent of the Flask app
    """

    from app.models import Analysis
    from config import Config
    
    config = Config() 


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
        get_running_vms = vmware_linux_get_running_vms
    else:
        print("Unknown VM provider: {}".format(vm_provider))

    # get VMs from config
    vms = config.VMS

    # initialize VMs by resetting to snapshot
    for vm in vms:
        reset_snapshot(vm['name'], vm['snapshot'])

    # wait until VMs are ready
    running_vms = get_running_vms()
    while len(running_vms) > 0:
        time.sleep(1)
        running_vms = get_running_vms()

    # start VMs
    for vm in vms:
        start_vm(vm['name'])

    # set up database connection
    engine = sqlalchemy.create_engine(config.SQLALCHEMY_DATABASE_URI)
    Session = sqlalchemy.orm.sessionmaker(bind=engine)
    session = Session()
    
    # loop to monitor VMs
    while True:
        try:
            # get all analyses currently running
            session.commit()
            analyses = session.query(Analysis).filter(Analysis.status == 1).all()

            # check if time since the date_updated time of the analysis is greater than the timeout time
            for analysis in analyses:
                # get current time
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
                    for vm in vms:
                        if vm['name'] == analysis.analysis_vm:
                            snapshot = vm['snapshot']
                            break
                    reset_snapshot(analysis.analysis_vm, snapshot)
                    
                    # wait until VM is ready
                    running_vms = get_running_vms()
                    while analysis.analysis_vm in running_vms:
                        logging.debug(f"Waiting for VM {analysis.analysis_vm} to reset")
                        time.sleep(1)
                        running_vms = get_running_vms()

                    # start VM
                    start_vm(analysis.analysis_vm)

                    # log
                    logging.info(f"Reset VM {analysis.analysis_vm} for analysis {analysis.id} due to timeout")

        except Exception as e:
            logging.error(f"Error in monitor loop: {e}")

        # sleep for 10 seconds
        time.sleep(10)    

if __name__ == '__main__':
    main()