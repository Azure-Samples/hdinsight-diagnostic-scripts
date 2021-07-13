# HDInsight Network Validator (a.k.a HNV) v2.0

## Table of Contents
<li> What does it do ?
<li> Requirements
<li> Usage
<li> Not supported scenarios
<li> How it works ?
<li> Troubleshooting
<br><br>

## What does it do ?
Creating an HDInsight cluster in a complex networking environment that involves firewall, UDR etc. requires configuring multiple settings properly. HDInsight cluster creation can fail if your network is not configured properly.<br>
HDInsight Network Validator (a.k.a HNV) is a Python 3.x script checks these settings and reports back if your network is properly configured to create and use an HDInsight cluster or not.

### HNV supports the two main scenarios below:

- #### <u>Scenario A : Before creating an HDInsight cluster</u>
  You haven't created your HDInsight cluster yet and you want to do a pre-validation. For this scenario, tool expects you to supply the values to the parameters in conf/params.conf file. Check "Usage" part below for details

- #### <u>Scenario B - Already created your HDInsight cluster and want to validate your network settings</u>
  After you created your HDInsight cluster and have started using, it's possible that your network settings might have changed by you or someone else. You may have various problems in various scenarios when working with your cluster because of those "unknown" changes. You can use HNV to find those "unknown" changes to fix.
  For this scenario, tool expects you to supply the CLUSTER_DNS_NAME in params.conf file. When you ran the tool, it will ask you to enter your HDInsight SSH username and password to be able to SSH into your headnode to gather all the necessary details from your cluster. If you don't want SSH user and password to be asked in your consequent runs, you can put them in CLUSTER_SSHUSER and CLUSTER_SSHUSER_PASS parameters in the params.conf file.<br> 
  P.S.: Don't forget to remove all those after you're done using HNV! Better you may want to delete the VM as a whole.

For both scenario A and B, HNV checks the below components if they're configured correctly for Azure HDInsight or not:
1. Network Security Group (NSG) in the subnet
2. Using Azure Firewall and User Defined Route (UDR)
3. Using non-Azure Firewall Networking Virtual Appliance (NVA) and User Defined Route : Although tool can obtain the firewall rules and checks if you are using Azure Firewall, it won't be able to gather firewall rules from an NVA other than Azure Firewall. But the tool still will do inbound/outbound checks in Part 2

## Requirements:
<li>HNV requires you to create an <a href="https://portal.azure.com/?feature.customportal=false#create/Canonical.UbuntuServer1804LTS-ARM">Ubuntu Server 18.04 LTS Azure Linux VM</a> in the subnet that you are planning to create the HDInsight cluster, or the subnet that you used for your HDInsight cluster if you've created your HDInsight cluster already. Also, VM must be created in the same region as your HDInsight cluster. 
You can use as low as a B1s (1G RAM, 1 vCore) for the VM size or bigger. When you are done with HNV, don't forget to delete this VM. If you are planning to use it again, you may want to "Stop" the VM to avoid charges.
<li>You will need to create a <a href="https://docs.microsoft.com/en-us/python/api/overview/azure/hdinsight?view=azure-python#authentication-example-using-a-service-principal">Azure Service Principal</a> for the tool to access resources in your subscription
<li><a href="https://docs.microsoft.com/en-us/azure/network-watcher/network-watcher-monitoring-overview">Azure Network Watcher</a> : HNV uses OS built-in "nc" tool to do an actual "outbound" access checks. For "inbound" access checks, it uses <a href="https://docs.microsoft.com/en-us/azure/network-watcher/diagnose-vm-network-traffic-filtering-problem#use-ip-flow-verify">IPFlowVerify</a> diagnostics feature of network watcher. If you already have a network watcher created in the region, HNV will find and use it. If you don't, HNV will create an network watcher in the region to use. When script finished, it will delete network watcher if HNV needed to create one. 
1000 network diagnostic tool usage per month is Free in Azure Network Watcher. Additional 1000 tool usage per month is $0.001 . Please check <a href="https://azure.microsoft.com/en-us/pricing/details/network-watcher/">Azure Network Watcher pricing</a> for more details
<br><br>




## Usage:
### 1 - Create "Service Principal": <br>
You will need to create a "Service Principal" following steps below (or by referring  <a href="https://docs.microsoft.com/en-us/python/api/overview/azure/hdinsight?view=azure-python">here</a> ) : 
 - Browse to Azure Cloud Shell in your browser https://shell.azure.com/bash
 - Run the command below in cloud shell to see your subscription information : <br>
 `az account show`
 - If you're not logged into the correct subscription, select the correct one by running:<br>
 `az account set -s <name or ID of subscription>`
 - If you have not already registered the HDInsight Resource Provider by another method (such as by creating an HDInsight Cluster through the Azure Portal), you need to do this once before you can authenticate : <br>
 `az provider register --namespace Microsoft.HDInsight`
 - Next, choose a name for your service principal and create it with the following command:<br>
 `az ad sp create-for-rbac --name "spHDInsightNetworkValidationScript" --sdk-auth`
 - Command above will return the service information as JSON. Copy this JSON output to a secure/safe place as it contains the secret for your service principal.

P.S. : If you receive a permission error after running the commands above, you need to contact your subscription owner and ask them to run the commands and share the output JSON with you.

When running tool, it will ask you to paste this service principal JSON in each run. If you prefer, you can save the output JSON into a file like "config/mysp.json" and set SP_JSON_FILE="config/mysp.json" in config/params.conf file. So HNV will read the service principal details from the file. 
After you're done with the tool, you need to make sure that you remove this config/mysp.json file as it contains  secret for your service principal.

### 2 - Create Ubuntu VM
- Create an <a href="https://portal.azure.com/?feature.customportal=false#create/Canonical.UbuntuServer1804LTS-ARM">Ubuntu Server 18.04 LTS Azure Linux VM</a> in the subnet that you are planning to create the HDInsight cluster, or the subnet that you used for your HDInsight cluster if you created HDInsight cluster already. Also, VM must be created in the same region as your HDInsight cluster. 
You can use as low as a B1s (1G RAM, 1 vCore) VM size or bigger. When you are done  with HNV, don't forget to delete this VM. If you are planning to use it again, you may want to "Stop" the VM to avoid charges.
- When creating the VM, be sure that you selected the same VNet/Subnet you are planning to create the HDInsight cluster. 
- When setting NSG for your VM's NIC card, you should select the same NSG you use in the subnet or "None". If you select your subnet NSG and your subnet NSG does not allow SSH access to TCP 22, you need to add it to your subnet NSG. So you can SSH into the VM.

### 3 - Clone HNV from repo
After creating the VM, you need to follow the steps below :
- SSH into the VM
- Run the command  below to get the HNV tool:<br>
`git clone https://github.com/Azure-Samples/hdinsight-diagnostic-scripts.git`
- You will need to run the commands below only once to install the necessary Ubuntu and Python packages: <br>
  ```
  cd HDInsightNetworkValidator
  sudo chmod +x ./setup.sh
  sudo ./setup.sh
  ```

### 4 - Edit conf/params.conf configuration file with a text editor (like Vi, Nano etc)
#### For <u>Scenario A (Before creating an HDInsight cluster)</u>, tool expects you to supply the values to the parameters below in conf/params.conf file:
  - VM_RG_NAME : Resource Group name of the Ubuntu VM
  - PRIMARY_STORAGE : Primary storage acount name (without .blob.core.windows.net , .dfs.core.windows.net etc).
  - SECONDARY_STORAGE : Secondary storage acount name if you will use. If not, leave empty  
  - AMBARIDB/HIVEDB/OOZIEDB : Azure SQL Server names for your custom AMBARIDB/HIVEDB/OOZIEDB servers. If you are going to use default AMBARIDB/HIVEDB/OOZIEDB metastore supplied by HDInsight, leave it empty
  - KAFKA_REST_PROXY : If you are going to create a <a href="https://docs.microsoft.com/en-us/azure/hdinsight/kafka/rest-proxy">Kafka Rest Proxy enabled Kafka cluster</a>, change it to "True", else leave it as "False"
  - KV1 : If you are going to use <a href="https://docs.microsoft.com/en-us/azure/hdinsight/disk-encryption">Bring Your Own Key (BYOK)</a>, put your Azure KeyVault name here . If not, leave it empty
   
   If you are going to use <a href="https://docs.microsoft.com/en-us/azure/hdinsight/domain-joined/hdinsight-security-overview">Enterprise Security Pack (ESP)</a>:

  - AADDS_DOMAIN : Your AAD-DS domain name. Leave it empty if you won't use ESP
    RANGERDB : Azure SQL Server name for your custom RangerDB server. If you are going to use default Ranger DB, leave it empty

#### For <u>Scenario B (You already have your HDInsight cluster created and want to validate your network settings)</u>, you need to enter CLUSTER_DNS_NAME in params.conf file. When you ran the tool, it will ask you to enter your HDInsight SSH username and password to be able to SSH into your headnode to gather all the necessary details from your cluster. If you don't want SSH user and password to be asked in your consequent runs, you can put them in CLUSTER_SSHUSER and CLUSTER_SSHUSER_PASS parameters in the params.conf file. 
P.S. : Don't forget to remove all those after you're done using HNV! Better you may want to delete the VM as a whole.

### 5 - Run HNV
+ Now you can use the tool with the command below
sudo ./HDInsightNetworkValidator.py

## Not Supported:
1. If you are using an NVA (Network Virtual Appliance) other than Azure Firewall
2. <a href="https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-private-link">"Private Link" enabled HDInsight cluster</a>

## Troubleshooting:
<li> Receiving error when running "./setup.sh"<br>
setup.sh installs a few packages with "apt" package manager and install Python libraries with pip. It's possible that your network admin does not allow traffic to the outside for apt and pip to install packages and libraries. 
You might ask your network admin to supply a proxy server that you can use accessing internet via a proxy server. Refer to https://askubuntu.com/questions/257290/configure-proxy-for-apt for further details on how to configure apt and/or other tools to work with your proxy server.
As we don't want HNV tool itself to go thorugh your proxy server, please don't forget to remove this proxy server setting after setup.sh successfully installed the python libraries with pip.

## How it works :
It consists of 4 parts:<br>
#### PART 1 - Gathering Information
  - Get the name of the current diagnostic VM  
  - Get the Region/Location, Private IP, DNS settings, VNet/Subnet of the diagnostic VM
  - Check the NSG rules in the subnet
  - Get the storage accounts and do the checks below for each: 
    - Check if "Secure Transfer Required" is set to "True"
    - Check if you are using storage firewall and if you are, checks if storage is configured for the current VNet to access
  - Create a Network Watcher in the region, if there is none
  - Check what is the NextHop set for 8.8.8.8
    - If nexthop is set to "Internet", understands that you are not using Azure Firewall or another NVA
    - if nexthop is set to "VirtualAppliance", it gets this Private IP that it's set for nexthop and enumarates Azure Firewalls in the subscription. If it matches with the PRivate IP, gets the Azure Firewall resource.
       - As you are using a firewall/NVA, gets your UDR
       - If it's Azure Firewall checks Application Rule Collections and Network Rule Collections

#### PART 2 - Add Validations:
- In this part, tool adds the necessary inbound sources, which are HDInsight Management Endpoints, and outbound destinations to its list depending on what's obtained in the previous part.

#### PART 3 - Execute the validations:   
- Do the actual validations populated in Part 2. It uses "nc" command for the outbound validation executions and network watcher's IpFlowVerify tool for inbound validation executions.

#### SUMMARY - Results:
- Show the results
