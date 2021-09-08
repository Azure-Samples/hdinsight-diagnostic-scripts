from lib.utils import *


def getCurrentVM(self):
    """Find the current VM details in Azure"""

    current_vm = ""

    vms = self.compute_client.virtual_machines.list(self.current_vm_rg.name)
    vmCount = 0
    for vm in vms:
        vmCount = vmCount + 1
        if vm.name == self.vm_hostname:
            current_vm = vm
            break

    # Could not find the VM, ask user
    if current_vm == None:
        # Ask user to select the current VM
        vmNumber = input("Enter the number in front of the VM name : ")
        # if (vmNumber == ''): vmNumber = '1'
        # vmNumber = 1  #Picking first VM for dev purposes

        # As we receive "'ItemPaged' object does not support indexing", we have to loop through the VMs once more
        vmCount = 0
        vms = self.compute_client.virtual_machines.list(self.current_vm_rg.name)
        for vm in vms:
            vmCount = vmCount + 1
            if vmCount == int(vmNumber):
                current_vm = vm
                break
        printAndLog(self, "Selected VM is : " + current_vm.name)

    return current_vm


def getCurrentVMsNIC(self):
    """Get the ARM resource ID of the NIC of the selected vm. We pick the 1st NIC"""
    nic_id = self.current_vm.network_profile.network_interfaces[0].id

    # From the NIC ARM resource ID, we get the NIC name as it's the last string when we split by '/' chars
    nic_name = nic_id.split("/")[-1]

    # Now we can get NIC object using nic_name
    nic = self.network_client.network_interfaces.get(self.current_vm_rg.name, nic_name)
    return nic


def getCurrentVMsIP(self):
    """Get current VMs IP from NIC. We get 1st private IP address"""
    current_subnet_id = self.current_vm_nic.ip_configurations[0].subnet.id
    current_subnet_name = current_subnet_id.split("/")[-1]
    current_vnet_name = current_subnet_id.split("/")[-3]

    # Again we assume the 1st IP in the NIC is our VM's IP address
    current_vm_ip = self.current_vm_nic.ip_configurations[0].private_ip_address

    return current_vm_ip


# def createVM(compute_client, network_client, RESOURCE_GROUP):
#     #https://github.com/Azure-Samples/virtual-machines-python-manage/blob/master/example.py
