import sys
import os
import logging
import time
import json
import maskpass
from colorama import *
from halo import Halo
from prettytable import PrettyTable

from lib.utils import *
from lib.storage import *
from lib.scrapers import *
from lib.hdinsight import *
from lib.validation import *
from lib.azurefirewall import *
from lib.network import *
from lib.compute import *

from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.hdinsight import HDInsightManagementClient
from azure.mgmt.hdinsight.models import *

# from azure.storage.blob import BlobServiceClient              #WASB
# from azure.storage.filedatalake import DataLakeServiceClient  #ADLSGen2


class HDInsightNetworkValidator:

    # Globals
    scriptVersion = "2.0.0 - Final"
    verboseMode = False

    # Parameters dictionary
    params = {}
    logger = ""

    # Contains region name and service tag name for the region . Example 'australiacentral':'HDInsight.AustraliaCentral', etc.
    azurePublicCloudRegionNames = {}

    # List containing the storage accounts
    storageAccounts = []

    # regionName = '' #For ex: "eastus"
    # regionDisplayName = '' #For ex: "East US"

    # credential = ''
    # subscription_id = ''
    # compute_client = None
    # network_client = None
    # resource_client = None
    # blobservice_client = None
    # datalakeservice_client = None
    # hdinsight_client = None

    # Service Tags JSON file
    # serviceTagsJSONFileName = ''

    # vm_hostname = ''
    # current_vm = None #VirtualMachine()
    current_vm_rg = None  # ResourceGroup()
    # current_vm_ip = '' #
    # current_vm_nic = None #NetworkInterface()

    # current_vnet = None #VirtualNetwork()
    current_vnet_rg = None  # ResourceGroup()
    # current_subnet = None #Subnet()
    # current_subnet_name = ''
    vnet_is_using_custom_dns = False

    # ----
    # current_subnet_nsg_name = ''
    # current_subnet_nsg_rg_name = ''
    # current_subnet_nsg = None #SecurityGroup()

    isNSGServiceTagsAreCorrect = False  # True if "Service Tags" are right
    isNSGIPsAreCorrect = False  # True if HDIME IPs are added manually and correct

    # current_nw = None #NetworkWatcher()
    # current_nw_rg_name = ''
    # current_route_table = None #RouteTable()
    # current_next_hop_ip = ''
    # current_azure_firewall = '' #AzureFirewall()
    allowAllOutboundRuleExistsInAzureFirewall = False

    # hdinsight_cluster = '' #Cluster()
    isKafka = False  # Used in HiveDB/OozieDB checks as there is no HiveDB or OozieDB in Kafka clusters
    kafkaRestProxyEnabled = False
    cluster_headnode_ips = {}
    cluster_details = {}  # Dictionary containing the cluster details obtained by SSHing to the cluster

    # HDInsight Management Endpoint IPs for current region obtained from docs (P.S.: NOT from Service Tag JSON file!)
    CURRENT_REGION_HDIME_IPS = {}

    # List to store all 'Validation' objects
    validations = []

    totalValidationCount = 0
    failedValidationCount = 0

    def main(self):
        # Initialize logger
        self.logger = initializeLogger(self)
        self.logger.info("------------------------------------------------------------------------------")

        # Print banner
        printAndLog(self, Fore.YELLOW + "==================================")
        printAndLog(self, Fore.YELLOW + "HDInsight Network Validator  v" + self.scriptVersion)
        printAndLog(self, Fore.YELLOW + "==================================")

        # Read config from parameters file
        # TODO : Error check
        self.params = getParamsFromConf(self)

        # Print if user used -v (verbose mode) switch
        if self.verboseMode:
            printAndLog(self, "Verbose mode: " + Fore.GREEN + "On" + Style.RESET_ALL)
        else:
            printAndLog(self, "Verbose mode: " + Fore.GREEN + "Off" + Style.RESET_ALL)

        # Get current VM
        self.vm_hostname = getHostName()
        self.logger.info('getHostName() returned "' + self.vm_hostname + '"')

        # Get "Credential" using "Service Principal"
        self.credential = getDefaultCredential(self)

        # Create "***Client"s using "Credential" and Subscription Id
        self.subscription_id = os.environ["SUBSCRIPTION_ID"]
        self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)
        self.network_client = NetworkManagementClient(self.credential, self.subscription_id)
        self.resource_client = ResourceManagementClient(self.credential, self.subscription_id)
        self.storage_client = StorageManagementClient(self.credential, self.subscription_id)
        self.hdinsight_client = HDInsightManagementClient(self.credential, self.subscription_id)
        # self.blobservice_client = BlobServiceClient(self.credential, self.subscription_id)
        # self.datalakeservice_client = DataLakeServiceClient(self.credential, self.subscription_id)

        # Initialize validation counts
        self.totalValidationCount = 0
        self.failedValidationCount = 0

        printAndLog(self, "")
        printAndLog(self, "--------------------------------------------")
        printAndLog(self, Fore.CYAN + "A) Gathering info and making inital controls  ")
        printAndLog(self, "--------------------------------------------")

        self.hdinsight_cluster = None
        self.getHDInsightClusterIfItsAlreadyCreated()

        # Check if the VM RG name supplied in config file really exists. If not, enumerate all RGs and allow customer to pick the correct RG
        listResourceGroupsAnswer = "n"
        if self.params["VM_RG_NAME"] != "":
            resource_groups = self.resource_client.resource_groups.list()
            for rg in resource_groups:
                if self.params["VM_RG_NAME"] == rg.name:
                    self.current_vm_rg = rg
                    break
        if self.current_vm_rg == None:
            printAndLog(
                self,
                'Cannot find a resource group named "' + self.params["VM_RG_NAME"] + '" under your "' + self.subscription_id + '" subscription id',
            )
            listResourceGroupsAnswer = input("Do you want me to list all the resource groups in this subscription (y)/n ? ")

            # if (listResourceGroupsAnswer == 'y' or listResourceGroupsAnswer == '' ):
            #     printAndLog(self,'Below are the resource groups in this subscription : ')
            #     resource_groups = self.resource_client.resource_groups.list()
            #     for rg in resource_groups:
            #         printAndLog(self,rg.name)
            # else:
            #     printAndLog(self,'Exiting ...')

            if listResourceGroupsAnswer == "n":
                printAndLog(self, "Exiting ...")
                sys.exit()
            else:
                listResourceGroupsAnswer = "y"

        if self.current_vm_rg == None or listResourceGroupsAnswer == "y":
            printAndLog(self, "Select the resource group your VM is created under: ")
            rgCount = 0
            resource_groups = self.resource_client.resource_groups.list()
            for rg in resource_groups:
                rgCount = rgCount + 1
                printAndLog(self, str(rgCount) + " - " + rg.name + " " + rg.location)

            # Ask user to select the current RG
            rgNumber = input("Enter the number in front of the RG name : ")
            # rgNumber = 73  #Picking "farukc-RG" rg for dev purposes

            # As we receive "'ItemPaged' object does not support indexing", we have to loop through the RGs once more
            rgCount = 0
            resource_groups = self.resource_client.resource_groups.list()
            for rg in resource_groups:
                rgCount = rgCount + 1
                if rgCount == int(rgNumber):
                    self.current_vm_rg = rg
                    break
            printAndLog(self, '"' + self.current_vm_rg.name + '" resource group is selected\n')

            # update the "VM_RG_NAME" in params.conf file
            f = open("config/params.conf", "r")
            lines = f.readlines()
            line_index = -1
            for line in lines:
                line_index = line_index + 1
                if line.startswith("VM_RG_NAME"):
                    lines[line_index] = 'VM_RG_NAME="' + str(self.current_vm_rg.name) + '"\n'
            f = open("config/params.conf", "w")
            f.writelines(lines)
            f.close()

            printAndLog(self, '"' + self.current_vm_rg.name + '" resource group is corrected in config file\n')

        self.current_vm = getCurrentVM(self)
        if self.verboseMode:
            showTextWithIcon(self, 'Current VM name: "' + Fore.GREEN + self.current_vm.name + '"' + Style.RESET_ALL)

        self.regionName = self.current_vm.location
        if self.verboseMode:
            showTextWithIcon(self, 'Current region : "' + Fore.GREEN + self.regionName + '"' + Style.RESET_ALL)

        # Get Service Tags JSON file
        self.serviceTagsJSONFileName = getServiceTagsJSONFileName(self)
        self.logger.info('Service Tags JSON FileName is "' + self.serviceTagsJSONFileName + '"')

        # Check if the VM's location is Azure Public cloud or not
        # To get the short region names in Azure Public Cloud, we are getting HDIME_IPs in advance. So it will download the "ServiceTags_Public_XXXXYYZZ.json" file (or reuse the existing one if it's already downloaded before)

        # Get Azure Public Cloud region names from ServiceTagsJSONFile
        self.azurePublicCloudRegionNames = getAzurePublicCloudRegionNamesFromServiceTagsJSONFile(self)
        # printAndLog(self,self.azurePublicCloudRegionNames)

        # Check if the VM is in a region in Azure Public Cloud
        if not (self.regionName in self.azurePublicCloudRegionNames):
            printAndLog(self, 'This tool does not support "' + self.regionName + '" region yet ')
            sys.exit()

        # Get VM's NIC
        self.current_vm_nic = getCurrentVMsNIC(self)

        # Get VM's IP
        self.current_vm_ip = getCurrentVMsIP(self)

        # Get subnet name through the NIC
        current_subnet_id = self.current_vm_nic.ip_configurations[0].subnet.id
        self.current_subnet_name = current_subnet_id.split("/")[-1]

        # Get VNet
        self.current_vnet = getCurrentVNet(self)

        # Get VNet RG
        self.current_vnet_rg = getCurrentVNetsResourceGroup(self)

        # Get Subnet
        self.current_subnet = getCurrentSubnet(self)
        if self.verboseMode:
            showTextWithIcon(self, 'VNet/subnet: "' + Fore.GREEN + self.current_vnet.name + "/" + self.current_subnet.name + '"' + Style.RESET_ALL)
            showTextWithIcon(self, 'VNet IP CIDR: "' + Fore.GREEN + self.current_vnet.address_space.address_prefixes[0] + Style.RESET_ALL + '", Subnet IP CIDR : "' + Fore.GREEN + self.current_subnet.address_prefix + '"' + Style.RESET_ALL)

        # Get DNS servers from the VNet
        if self.current_vnet.dhcp_options == None:
            self.vnet_is_using_custom_dns = False
            if self.verboseMode:
                showTextWithIcon(self, "You are using " + Fore.GREEN + "Azure DNS servers" + Style.RESET_ALL + " in this VNet")
        else:
            self.vnet_is_using_custom_dns = True
            if self.verboseMode:
                showTextWithIcon(self, "You are using custom DNS servers : " + Fore.GREEN + str(self.current_vnet.dhcp_options.dns_servers) + Style.RESET_ALL + " in this VNet")

        # If HDInsight cluster name is supplied by customer, check if the VM is in the same subnet with HDInsight cluster
        if self.params["CLUSTER_DNS_NAME"] != "":
            if self.hdinsight_cluster.properties.compute_profile.roles[0].virtual_network_profile.subnet != self.current_subnet.id:
                hdi_subnet = self.hdinsight_cluster.properties.compute_profile.roles[0].virtual_network_profile.subnet
                showTextWithIcon(self, 'Your HDInsight cluster is in "' + hdi_subnet.split("/")[8] + "/" + hdi_subnet.split("/")[10] + '" VNet/Subnet. But this VM is in "' + self.current_subnet.id.split("/")[8] + "/" + self.current_subnet.id.split("/")[10] + '" VNET/Subnet. They need to be in the same VNet/Subnet. Exiting...', "line", "warn")
                sys.exit()

        self.getHDIMEIPs()
        self.doSubnetNSGCheck()

        self.doVMNICNSGCheck()

        self.doStorageAccountChecks()

        self.getNetworkWatcher()
        self.doNextHopCheck()

        self.doSqlServiceEndpointChecks()

        self.doFirewallChecks()
        self.addValidations()
        self.doValidations()
        self.showResult()
        self.doCleanup()

    def getHDInsightClusterIfItsAlreadyCreated(self):
        """Get the HDInsight cluster if it's already created"""
        if self.params["CLUSTER_DNS_NAME"] != "":
            self.logger.info("clusterDNSName : " + self.params["CLUSTER_DNS_NAME"])
            showTextWithIcon(self, 'Collecting information about your HDInsight cluster "' + self.params["CLUSTER_DNS_NAME"] + '" ...')

            self.hdinsight_cluster = getCluster(self)

            if self.hdinsight_cluster != None:
                self.logger.info("Cluster type: " + self.hdinsight_cluster.properties.cluster_definition.kind)
                if self.hdinsight_cluster.properties.cluster_definition.kind == "KAFKA":
                    self.isKafka = True

                if self.hdinsight_cluster.properties.kafka_rest_properties != None:
                    self.kafkaRestProxyEnabled = True
                    self.logger.info("Kafka Rest Proxy is enabled")

            # self.hdinsight_cluster.properties.cluster_definition.kind == 'KAFKA', 'SPARK'
            # self.hdinsight_cluster.properties.cluster_definition.component_version == {'Spark': '2.4'}
            # self.hdinsight_cluster.properties.cluster_version == '4.0.2000.1'

            if self.hdinsight_cluster == None:
                printAndLog(self, 'There is no HDInsight cluster named "' + self.params["CLUSTER_DNS_NAME"] + '" under this subscription')
                sys.exit()

            if self.hdinsight_cluster.properties.cluster_state != "Running":
                printAndLog(self, 'Your HDInsight cluster "' + self.hdinsight_cluster.name + '" is currently in "' + self.hdinsight_cluster.properties.cluster_state + '" state. It needs to be in "Running" state')
                printAndLog(self, "Exiting ...")
                sys.exit()

        if (self.params["CLUSTER_DNS_NAME"] == "") and (self.params["KAFKA_REST_PROXY"] == "True"):
            self.kafkaRestProxyEnabled = True
            showTextWithIcon(self, "As you have set KAFKA_REST_PROXY as True in config file, will assume that you are going to create a Kafka cluster with Kafka REST Proxy enabled option")

    def getHDIMEIPs(self):
        """Get HDInsight Management Endpoint IPs"""

        # Get 4 Global HDInsight Management Endpoint (HDIME) IPs from docs
        getHDInsightManagementEndpointIPsFromDocs(self)
        # printAndLog(self,self.params['FOUR_GLOBAL_HDIME_IPS'])
        # printAndLog(self,self.params['ALL_REGIONAL_HDIME_IPS'])

        # FOUR_GLOBAL_HDIME_IPS : 'list' is saved as string. we should read it back using
        if isinstance(self.params["FOUR_GLOBAL_HDIME_IPS"], str):
            self.params["FOUR_GLOBAL_HDIME_IPS"] = self.params["FOUR_GLOBAL_HDIME_IPS"].replace("[", "").replace("]", "").replace("'", "").replace(" ", "").split(",")

        # ALL_REGIONAL_HDIME_IPS : 'dictionary'  is saved as string, we should read it back using json loads (after converting single quotes to double quotes in the string)
        if isinstance(self.params["ALL_REGIONAL_HDIME_IPS"], str):
            self.params["ALL_REGIONAL_HDIME_IPS"] = json.loads(self.params["ALL_REGIONAL_HDIME_IPS"].replace("'", '"'))

        # What if user is not using Service Tags and adding HDIME IPs manually (old school way)
        self.CURRENT_REGION_HDIME_IPS = getHDInsightManagementEndpointIPsForCurrentRegion(self)

    def doSubnetNSGCheck(self):
        """Check subnet NSG if any"""

        resultDict = None

        if self.current_subnet.network_security_group == None:
            # if self.verboseMode:
            showTextWithIcon(self, "Subnet NSG : There is no NSG set in current subnet")
            printAndLog(self, "Exiting as there is nothing to check")
            sys.exit()
        else:
            self.current_subnet_nsg_name = self.current_subnet.network_security_group.id.split("/")[-1]
            self.current_subnet_nsg_rg_name = self.current_subnet.network_security_group.id.split("/")[4]
            self.current_subnet_nsg = getNSG(self.current_subnet_nsg_rg_name, self.current_subnet_nsg_name, self)

            if self.verboseMode:
                showTextWithIcon(self, 'Subnet NSG: You have an NSG named "' + Fore.GREEN + self.current_subnet_nsg_name + Style.RESET_ALL + '" set for current subnet')

            # Get the subnet NSG rules
            self.current_subnet_nsg_rules = getSubnetNSGRules(self)

            showTextWithIcon(self, "Subnet NSG rules check - Started ...", "line", "info")

            # Check if the subnet NSG rules has any HDInsight Service Tag or not
            if not (checkSubnetNSGRulesIfItHasAnyHDInsightServiceTags(self)):
                message = '   You don\'t have "HDInsight" or "HDInsight.regionname" service tags used in any of your subnet NSG rules. We recommend using service tags instead of adding HDInsight Management Endpoint (HDIME) IPs one-by-one.\n'
                message = message + "   But in case you can't use service tags for a reason, we'll check if you have added required HDInsight Management Endpoint IPs below: \n"
                message = message + Fore.GREEN + "    Global " + Style.RESET_ALL + "HDIME IPs : " + str(self.params["FOUR_GLOBAL_HDIME_IPS"]) + "\n"
                message = message + Fore.GREEN + "    Regional (" + self.regionName + ") " + Style.RESET_ALL + "HDIME IPs : " + str(self.CURRENT_REGION_HDIME_IPS)
                if self.verboseMode:
                    printAndLog(self, message)
                else:
                    self.logger.info(message)

                # Start checking IPs
                resultDict = checkSubnetNSGRulesForHDIMEIPs(self)

                isAllHDIMEIPsOKForPort443 = False
                if self.kafkaRestProxyEnabled:
                    isAllHDIMEIPsOKForPort9400 = False

                if all(x.isOk == True for x in resultDict["443"].values()):
                    isAllHDIMEIPsOKForPort443 = True
                if self.kafkaRestProxyEnabled:
                    if all(x.isOk == True for x in resultDict["9400"].values()):
                        isAllHDIMEIPsOKForPort9400 = True

                if self.kafkaRestProxyEnabled:
                    # if resultDict["443"] and resultDict["9400"]:
                    if isAllHDIMEIPsOKForPort443 and isAllHDIMEIPsOKForPort9400:
                        self.isNSGIPsAreCorrect = True
                else:
                    # if resultDict["443"]:
                    if isAllHDIMEIPsOKForPort443:
                        self.isNSGIPsAreCorrect = True

                msg = "Subnet NSG rules check - Result : "
                if self.isNSGIPsAreCorrect:
                    # printAndLog(self, "Subnet NSG rules check - Result : HDIME IPs " + str(self.params["FOUR_GLOBAL_HDIME_IPS"]) + " ; " + str(self.CURRENT_REGION_HDIME_IPS) + " are added correctly. OK!")
                    msg = msg + "HDIME IPs " + str(self.params["FOUR_GLOBAL_HDIME_IPS"]) + " ; " + str(self.CURRENT_REGION_HDIME_IPS) + " are added correctly. OK!"
                    showTextWithIcon(self, msg, "line", "succeed")
                else:
                    if self.kafkaRestProxyEnabled:
                        if isAllHDIMEIPsOKForPort443:
                            # printAndLog(self, "HDIME IPs " + str(self.params["FOUR_GLOBAL_HDIME_IPS"]) + " ; " + str(self.CURRENT_REGION_HDIME_IPS) + " are NOT added correctly. Although you have allowed access for TCP 443 port from the IPs, Kafka Rest Proxy 9440 port access is NOT allowed. KO!")
                            msg = msg + "HDIME IPs " + str(self.params["FOUR_GLOBAL_HDIME_IPS"]) + " ; " + str(self.CURRENT_REGION_HDIME_IPS) + " are NOT added correctly. Although you have allowed access for TCP 443 port from the IPs, Kafka Rest Proxy 9440 port access is NOT allowed"
                            showTextWithIcon(self, msg, "line", "fail")

                        elif isAllHDIMEIPsOKForPort9400:
                            # printAndLog(self, "HDIME IPs " + str(self.params["FOUR_GLOBAL_HDIME_IPS"]) + " ; " + str(self.CURRENT_REGION_HDIME_IPS) + " are NOT added correctly. Although you have allowed access for Kafka Rest Proxy TCP 9400 port from the IPs, 443 port access is NOT allowed. KO!")
                            msg = msg + "HDIME IPs " + str(self.params["FOUR_GLOBAL_HDIME_IPS"]) + " ; " + str(self.CURRENT_REGION_HDIME_IPS) + " are NOT added correctly. Although you have allowed access for Kafka Rest Proxy TCP 9400 port from the IPs, 443 port access is NOT allowed"
                            showTextWithIcon(self, msg, "line", "fail")
                    else:
                        # printAndLog(self, "  Subnet NSG rules check - Result : Some or all of the HDIME IPs below are NOT added correctly. You need to grant access for TCP 443 port from all the IPs : ")
                        msg = msg + "Subnet NSG rules check - Result : Some or all of the HDIME IPs below are NOT added correctly. You need to grant access for TCP 443 port from all the IPs : "
                        showTextWithIcon(self, msg, "line", "fail")

                        # Show the IPs in a PrettyTable
                        pt = PrettyTable(["IP", "Port", "Scope", "Added or not"])
                        for hdime_ip_validation in resultDict["443"].values():
                            strAddedOrNot = ""
                            if hdime_ip_validation.isOk:
                                strAddedOrNot = "✔"
                            else:
                                strAddedOrNot = "✖"

                            if hdime_ip_validation.isOk:
                                pt.add_row([hdime_ip_validation.HDIMEIP, str(hdime_ip_validation.Port), hdime_ip_validation.Scope, Fore.GREEN + strAddedOrNot + Style.RESET_ALL])
                            else:
                                pt.add_row([hdime_ip_validation.HDIMEIP, str(hdime_ip_validation.Port), hdime_ip_validation.Scope, Fore.RED + strAddedOrNot + Style.RESET_ALL])
                        printAndLog(self, pt)

            else:
                # Subnet NSG Rules has at least one HDInsight Service Tag. So, check if HDInsight service tags are correct or not.

                # SERVICE TAG checks etc.!!!!!!!!!!!!!!!!
                if self.verboseMode:
                    printAndLog(self, "  At least one NSG rule with HDInsight service tag is found.  ")
                self.params["SINGLE_REGIONAL_SERVICE_TAGS"] = getSingleRegionalServiceTagsFromDocs(self)
                # printAndLog(self,self.params['SINGLE_REGIONAL_SERVICE_TAGS'])
                # printAndLog(self,self.params['SINGLE_REGIONAL_SERVICE_TAGS_SHORT'])

                self.params["MULTIPLE_REGIONAL_SERVICE_TAGS_FOR_GROUP1"] = getMultipleRegionalServiceTagsForGroup1FromDocs(self)

                self.requiredServiceTags = getRequiredServiceTagsForCurrentRegion(self)
                printAndLog(self, "  For '" + Fore.GREEN + self.regionName + Style.RESET_ALL + "' region, you need to have the following service tags added into your NSG : " + Fore.GREEN + str(self.requiredServiceTags) + Style.RESET_ALL + " or you may use 'HDInsight' global service tag that covers all regions")

                self.isNSGServiceTagsAreCorrect = checkSubnetNSGRulesForServiceTags(self)

                if self.isNSGServiceTagsAreCorrect:
                    showTextWithIcon(self, "Subnet NSG rules check - Result: NSG service tags are configured correctly. OK!", "line", "succeed")
                else:
                    showTextWithIcon(self, "Subnet NSG rules check - Result: You have NSG service tags are NOT configured correctly. KO!", "line", "fail")

            # SERVICE TAG checks END!!!!!!!!!!

        # Show the subnet NSG rules for HDIME manual IP scenario
        if self.verboseMode and resultDict != None:
            printAndLog(self, "  Your subnet NSG rules are below as reference :")
            printAndLog(self, resultDict["allNSGRulesInPrettyTable"])

    def doVMNICNSGCheck(self):
        """VM NIC NSG Check"""
        spinnerText = "Check NSG in your VM's NIC"
        spinner = Halo(text=spinnerText, spinner="line", placement="left")

        if self.current_vm_nic.network_security_group == None:
            if self.verboseMode:
                spinner.text = "There is no NSG set on this current VM's NIC. OK!"
                # spinner.info()  #.info() generates "i" icon in "Blue". To be able to change the color, using .stop_and_persist()
                spinner.stop_and_persist(symbol=Fore.GREEN + "ℹ" + Fore.RESET, text=spinner.text)
                print("")
        else:
            if str(self.current_vm_nic.network_security_group.id) == str(self.current_subnet.network_security_group.id):
                if self.verboseMode:
                    # printAndLog(self,'   VM NIC NSG and Subnet NSG is same. OK!')
                    spinner.text = spinner.text + ". VM NIC NSG and Subnet NSG is same. OK!"
                    # spinner.info()  #.info() generates "i" icon in "Blue". To be able to change the color, using .stop_and_persist()
                    spinner.stop_and_persist(symbol=Fore.GREEN + "ℹ" + Fore.RESET, text=spinner.text)
                    print("")
            else:
                spinner.fail()
                printAndLog(self, "   ==> Exiting! Please make the necessary change below and rerun the tool after the change: ")
                printAndLog(self, '       You will need to change the VM NIC NSG to "None" or to the same NSG set for your subnet, which is "' + str(self.current_subnet.network_security_group.id) + '"')
                sys.exit()

    def doStorageAccountChecks(self):
        """Do Storage Account checks"""
        # Get storage accounts (either from params.txt or from HDInsight cluster directly)
        # Ref: https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-restrict-outbound-traffic#create-and-configure-a-route-table
        getStorageAccounts(self)

        # No storage accounts
        if not self.storageAccounts:
            showTextWithIcon(self, "You have not supplied primary storage account name with PRIMARY_STORAGE in params.txt file. Bypassing all checks and validations about storage accounts", iconType="warn")
        else:
            # Check if "Secure Transfer Required" is set for all storage accounts
            if self.verboseMode:
                spinnerText = "Check if " + Fore.GREEN + '"Secure Transfer Required"' + Style.RESET_ALL + " is set on the storage accounts "
                spinner = Halo(text=spinnerText, spinner="line", placement="left")
                # printAndLog(self,' + Checking rules in your Azure Firewall and UDR ...', end=" ")
                spinner.start()
                if checkSecureTransferRequiredIsSetForAllStorageAccounts(self):
                    spinner.text = spinnerText + ". OK!"
                    spinner.succeed()
                else:
                    spinner.text = ' - "Secure Transfer Required" is NOT set on below storage accounts: '
                    spinner.fail()
                    for storageAccount in self.storageAccounts:
                        if storageAccount.enable_https_traffic_only != True:
                            printAndLog(self, "   " + storageAccount.name + " " + str(storageAccount.kind) + " " + str(storageAccount.is_hns_enabled) + " " + str(storageAccount.primary_endpoints))
                spinner.stop()
                print("")

            # Check if Storage Account(s) have "Storage Account Firewall" enabled and current subnet is allowed
            if noFirewallEnabledInAnyStorageAccount(self):
                if self.verboseMode:
                    showTextWithIcon(self, " You don't have storage firewall enabled in any of your storage accounts")

            elif checkIfCurrentSubnetIsAllowedInAllStorageAccountsFirewallsIfEnabled(self):
                if self.verboseMode:
                    # printAndLog(self,' + You have some or all storage account(s) have firewall enabled and set correctly to allow access from the current VNet/subnet. OK!')
                    showTextWithIcon(self, " You have some or all storage account(s) have firewall enabled and set correctly to allow access from the current VNet/subnet. OK!")
            else:
                # printAndLog(self,' - Storage account(s) have firewall enabled and below storage accounts and none of their rules list below does not allow access from the current VNet/subnet : KO!')
                showTextWithIcon(self, " Storage account(s) have firewall enabled and below storage accounts and none of their rules list below does not allow access from the current VNet/subnet : KO!", "line", "warn")
                for storageAccount in self.storageAccounts:
                    if storageAccount.network_rule_set.virtual_network_rules:
                        for virtual_network_rule in storageAccount.network_rule_set.virtual_network_rules:
                            if not ("virtualNetworks/" + self.current_vnet.name + "/subnets/" + self.current_subnet.name) in virtual_network_rule.virtual_network_resource_id:
                                printAndLog(self, "   " + 'Storage Account name : "' + storageAccount.name + '" ' + ', Rule : "' + virtual_network_rule.virtual_network_resource_id + '"')

    def getNetworkWatcher(self):
        """Get Network Watcher"""
        spinnerText = 'Check Network Watchers in "' + self.regionName + '" region ... '
        spinner = Halo(text=spinnerText, spinner="line", placement="left")
        if self.verboseMode:
            # printAndLog(self,' + Check Network Watchers in "' + self.regionName + '" region ... ')
            spinner.start()
        self.current_nw = getNetworkWatcher(self, spinner)
        if self.verboseMode:
            spinner.text = 'Network watcher name : "' + Fore.GREEN + self.current_nw.name + '"' + Style.RESET_ALL
            # spinner.info()  #.info() generates "i" icon in "Blue". To be able to change the color, using .stop_and_persist()
            spinner.stop_and_persist(symbol=Fore.GREEN + "ℹ" + Fore.RESET, text=spinner.text)
            spinner.stop()
            print("")
        self.current_nw_rg_name = self.current_nw.id.split("/")[4]

    def doNextHopCheck(self):
        """NextHop check"""
        # NextHop check to 8.8.8.8 to see if the next hop is "Virtual Appliance"
        spinnerText = "Checking NextHop ... "
        spinner = Halo(text=spinnerText, spinner="line", placement="left")
        if self.params["NEXTHOP_CHECK_RESULT"] == "":
            spinner.start()
            nexthop_result = getNextHop(self, "8.8.8.8")
            spinner.info()
            spinner.stop()
            self.params["NEXTHOP_CHECK_RESULT"] = nexthop_result.next_hop_type
        else:
            if self.verboseMode:
                showTextWithIcon(self, "Passing NextHop check ... Last nexthop check datetime was : " + Fore.GREEN + time.ctime(int(str(self.params["NEXTHOP_CHECK_DATETIME"]).split(".")[0])) + " UTC" + Style.RESET_ALL)

        if self.params["NEXTHOP_CHECK_RESULT"] == "Internet":
            if self.verboseMode:
                showTextWithIcon(self, "Next hop from the current VM is '" + Fore.GREEN + self.params["NEXTHOP_CHECK_RESULT"] + Style.RESET_ALL + "'. This means that your Outbound traffic is NOT controlled by a Firewall/Virtual Network Appliance")
            self.current_route_table = None
            self.current_next_hop_ip = None
            self.azure_fw = None
        else:
            if self.verboseMode:
                showTextWithIcon(
                    self,
                    "Next hop from the current VM is a '" + Fore.GREEN + self.params["NEXTHOP_CHECK_RESULT"] + Style.RESET_ALL + "'. Your Outbound traffic is controlled by a Firewall/Virtual Network Appliance",
                )

            self.current_route_table = getRouteTable(self)
            self.current_next_hop_ip = getNextHopIP(self)
            self.azure_fw = getAzureFirewall(self)

    def doSqlServiceEndpointChecks(self):
        """SQL Service Endpoint Checks"""
        # Azure SQL Service Endpoint check for Firewall/NVA scenarios
        if self.params["NEXTHOP_CHECK_RESULT"] != "Internet":
            showTextWithIcon(self, "SQL 'Service Endpoint' check - Started ...")
            self.isAzureSQLOutboundAllowedByServiceEndpoint = False
            self.isAzureSQLOutboundAllowedByServiceEndpoint = checkSubnetServiceEndpointsForAzureSQL(self)

            if self.isAzureSQLOutboundAllowedByServiceEndpoint == False:
                # Azure Firewall
                if self.azure_fw != None:
                    printAndLog(self, '  As you are using Azure Firewall and you DON\'T have "Microsoft.Sql" service endpoint added for your subnet, you need to make sure that your Azure Firewall allows traffic to Azure SQL in the "Outbound" direction for TCP 1433 port and TCP 11000-11999 port range for *.database.windows.net')
                    printAndLog(self, '  But if you are going to use your own custom metastores for Ambari/Oozie/Hive/Ranger, you need to make sure that your Azure Firewall allows traffic to Azure SQL in the "Outbound" direction for TCP 1433 port and TCP 11000-11999 port range for your "YOURAZURESQLSERVER.database.windows.net" FQDNs only')
                    printAndLog(self, "  Check Rule5 in https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-restrict-outbound-traffic#configure-the-firewall-with-network-rules for more info\n")

                else:
                    # 3rd party NVA
                    printAndLog(self, '  You are using non-Azure Firewall and you DON\'T have "Microsoft.Sql" service endpoint added for your subnet. If you are going to use a default metastore for any of Ambari, Oozie, Hive or Ranger, you should add "Microsoft.Sql" you need to make sure that your Firewall allows traffic to Azure SQL in the "Outbound" direction for TCP 1433 port and TCP 11000-11999 port range for *.database.windows.net')
                    printAndLog(self, '  But if you are going to use your own custom metastores for Ambari/Oozie/Hive/Ranger, you need to make sure that your firewall allows traffic to Azure SQL in the "Outbound" direction for TCP 1433 port and TCP 11000-11999 port range for your "YOURAZURESQLSERVER.database.windows.net" FQDNs only')
                    printAndLog(self, "  Check https://docs.microsoft.com/en-us/azure/hdinsight/network-virtual-appliance for more info")

    def doFirewallChecks(self):
        """There is a firewall, do the checks"""
        if self.azure_fw != None:
            if self.verboseMode:
                showTextWithIcon(self, 'NextHop is an Azure Firewall named as "' + Fore.GREEN + self.azure_fw.name + Style.RESET_ALL + '" with private IP address ' + Fore.GREEN + self.current_next_hop_ip + Style.RESET_ALL + " . Be sure that you have followed https://docs.microsoft.com/en-us/azure/hdinsight/hdinsight-restrict-outbound-traffic")

            showTextWithIcon(self, "Check rules in your Azure Firewall and UDR - Started ...")
            msg = "Check rules in your Azure Firewall and UDR - Result : "
            if checkAzureFirewallRules(self):
                showTextWithIcon(self, msg + "OK!", "line", "succeed")
            else:
                showTextWithIcon(self, msg + "KO!", "line", "fail")

        # 3rd party NVA
        if self.current_next_hop_ip != None and self.azure_fw == None:
            printAndLog(self, ' + NextHop IP is "' + self.current_next_hop_ip + '", it is a VirtualAppliance but it is NOT an Azure Firewall. This tool does not support checking the firewall rules in a Network Virtual Appliance other than Azure Firewall')
            printAndLog(self, "   Be sure that you have followed https://docs.microsoft.com/en-us/azure/hdinsight/network-virtual-appliance")
            printAndLog(self, "   If you proceed with the validations below, actual validation results should help you seeing if your NVA is configured correctly or not")
        # printAndLog(self,'')

    def addValidations(self):
        """Add validations"""
        printAndLog(self, "")
        printAndLog(self, "-----------------------------------------")
        printAndLog(self, Fore.CYAN + "B) Connection checklist is being prepared")
        printAndLog(self, "-----------------------------------------")

        # (A) Add standard validations
        # Read the standard validations from JSON file
        with open("config/std_validations.json") as f:
            validationsJSON = json.load(f)

        # Parse the standard validations from JSON file
        for item in validationsJSON["validations"]:
            # Add validation to the list

            # Ignore NTP checks if the flag is set in params.txt
            if (item["type"] == "NTP") and (self.params["FLAG_IGNORE_NTP_SERVER_VALIDATIONS"] == "True"):
                pass
            else:
                self.validations.append(Validation(int(item["id"]), item["name"], item["tool"], item["afterClusterCreated"], item["hostname"], item["protocol"], int(item["port"]), "outbound", int(item["timeout"])))
                self.totalValidationCount = self.totalValidationCount + 1

        # printAndLog(self,str(self.totalValidationCount) + ' standard validations read from JSON file')

        # Add AzureDNS validation if customer is using AzureDNS
        if self.vnet_is_using_custom_dns == False:
            self.totalValidationCount = self.totalValidationCount + 1
            # self.validations.append( Validation( self.totalValidationCount, "Azure DNS (168.63.129.16) - TCP 53 ", "nc", "False", "168.63.129.16", "TCP", 53, 'outbound', 5) )
            # self.totalValidationCount = self.totalValidationCount + 1
            self.validations.append(Validation(self.totalValidationCount, "Azure DNS (168.63.129.16) - UDP 53 ", "nc", "False", "168.63.129.16", "UDP", 53, "outbound", 5))

        # Add validations for Storage Accounts
        storageAccountCount = 0
        for storageAccount in self.storageAccounts:
            storageAccountCount = storageAccountCount + 1
            self.totalValidationCount = self.totalValidationCount + 1
            self.validations.append(Validation(self.totalValidationCount, "Storage Account #" + str(storageAccountCount), "nc", "False", getFQDNFromHTTPURL(str(storageAccount.primary_endpoints.blob)), "TCP", 443, "outbound", 5))

        if self.params["CLUSTER_DNS_NAME"] == "":
            if self.params["AMBARIDB"] != "":
                self.totalValidationCount = self.totalValidationCount + 1
                self.validations.append(Validation(self.totalValidationCount, "AmbariDB Server Connectivity", "nc", "False", self.params["AMBARIDB"], "TCP", 1433, "outbound", 5))

            if not (self.isKafka):
                if self.params["HIVEDB"] != "":
                    self.totalValidationCount = self.totalValidationCount + 1
                    self.validations.append(Validation(self.totalValidationCount, "HiveDB Server Connectivity", "nc", "False", self.params["HIVEDB"], "TCP", 1433, "outbound", 5))

                if self.params["OOZIEDB"] != "":
                    self.totalValidationCount = self.totalValidationCount + 1
                    self.validations.append(Validation(self.totalValidationCount, "OozieDB Server Connectivity", "nc", "False", self.params["OOZIEDB"], "TCP", 1433, "outbound", 5))

            if self.params["RANGERDB"] != "":
                self.totalValidationCount = self.totalValidationCount + 1
                self.validations.append(Validation(self.totalValidationCount, "RangerDB Server Connectivity", "nc", "False", self.params["RANGERDB"], "TCP", 1433, "outbound", 5))

        if self.params["KV1"] != "":
            self.totalValidationCount = self.totalValidationCount + 1
            self.validations.append(Validation(self.totalValidationCount, "Key Vault Connectivity", "nc", "False", self.params["KV1"], "TCP", 443, "outbound", 5))

        # AADDS-DOMAIN check if supplied in params.txt
        if self.params["AADDS_DOMAIN"] != "":
            self.totalValidationCount = self.totalValidationCount + 1
            self.validations.append(Validation(self.totalValidationCount, "ESP - AAD-DS/LDAPS Connectivity", "nc", "False", self.params["AADDS_DOMAIN"], "TCP", 636, "outbound", 5))

        # (B) If HDInsight cluster is already created
        if self.params["CLUSTER_DNS_NAME"] != "" and self.hdinsight_cluster.properties.cluster_state == "Running":

            if self.params["CLUSTER_SSHUSER"] == "":
                strPrompt = 'Enter SSH username for your "' + self.params["CLUSTER_DNS_NAME"] + '" HDInsight cluster: '
                self.params["CLUSTER_SSHUSER"] = maskpass.askpass(prompt=strPrompt, mask="*")

            if self.params["CLUSTER_SSHUSER_PASS"] == "":
                strPrompt = "Enter SSH password: "
                self.params["CLUSTER_SSHUSER_PASS"] = maskpass.askpass(prompt=strPrompt, mask="*")

            self.cluster_headnode_ips = getClusterHeadnodeIPsFromSubnet(self)
            # printAndLog(self,self.cluster_headnode_ips)

            self.cluster_details = getClusterDetailsUsingSSH(self)
            # printAndLog(self,self.cluster_details)

            ambariDBServerName = self.cluster_details["ambariDBServerName"]
            # printAndLog(self,'AmbariDB server name : ' + ambariDBServerName)
            self.totalValidationCount = self.totalValidationCount + 1
            self.validations.append(Validation(self.totalValidationCount, "AmbariDB Server Connectivity", "nc", "False", ambariDBServerName, "TCP", 1433, "outbound", 5))

            # #Get storage account details from storage profile
            # !!!!!TODO: KAFKA
            #
            # storageaccount_index = 0
            # for storageaccount in self.hdinsight_cluster.properties.additional_properties['storageProfile']['storageaccounts']:
            #     storageaccount_index = storageaccount_index + 1
            #     self.totalValidationCount = self.totalValidationCount + 1
            #     self.validations.append( Validation( self.totalValidationCount, "Storage Account # " + str(storageaccount_index) + " Connectivity", "nc", "False", storageaccount['name'], "TCP", 443, 'outbound', 5) )

            if not (self.isKafka):
                # Get HiveDB details from /etc/hive/conf/hive-site.xml by SSHing
                hiveDBServerName = getSqlServerNameFromJDBCUrl(self.cluster_details["hiveDBServerName"])
                # printAndLog(self,'HiveDB SQL Server name : ' + hiveDBServerName)
                self.totalValidationCount = self.totalValidationCount + 1
                self.validations.append(Validation(self.totalValidationCount, "HiveDB Server Connectivity", "nc", "False", hiveDBServerName, "TCP", 1433, "outbound", 5))

                # Get OozieDB details from /etc/oozie/conf/oozie-site.xml by SSHing
                oozieDBServerName = getSqlServerNameFromJDBCUrl(self.cluster_details["oozieDBServerName"])
                # printAndLog(self,'OozieDB SQL Server name : ' + oozieDBServerName)
                self.totalValidationCount = self.totalValidationCount + 1
                self.validations.append(Validation(self.totalValidationCount, "OozieDB Server Connectivity", "nc", "False", oozieDBServerName, "TCP", 1433, "outbound", 5))

            # ESP cluster
            # if (self.cluster_details['isESP'] == 'true'):
            if self.cluster_details["aadds_domain"] != "":
                # ESP - Get RangerDB details from /usr/hdp/current/ranger-admin/conf/ranger-admin-site.xml by SSHing
                rangerDBServerName = getSqlServerNameFromJDBCUrl(self.cluster_details["rangerDBServerName"])
                # printAndLog(self,'ESP - RangerDB SQL Server name : ' + rangerDBServerName)
                self.totalValidationCount = self.totalValidationCount + 1
                self.validations.append(Validation(self.totalValidationCount, "ESP - RangerDB Server Connectivity", "nc", "False", rangerDBServerName, "TCP", 1433, "outbound", 5))

                # ESP - Get ldap_urls from /etc/ldap/ldap.conf by SSHing
                ldapServerNameAndPort = self.cluster_details["ldap_uri"]
                # printAndLog(self,"ldap servername and port : " + ldapServerNameAndPort)
                self.totalValidationCount = self.totalValidationCount + 1
                self.validations.append(Validation(self.totalValidationCount, "ESP - LDAP Server Connectivity", "nc", "False", ldapServerNameAndPort[8:].split(":")[0], "TCP", int(ldapServerNameAndPort[8:].split(":")[1]), "outbound", 5))

        # Add "Global" HDInsight Management Endpoint (HDIME) validations
        globalIPIndex = 0
        for HDIME_IP in self.params["FOUR_GLOBAL_HDIME_IPS"]:
            globalIPIndex = globalIPIndex + 1
            self.totalValidationCount = self.totalValidationCount + 1
            self.validations.append(Validation(self.totalValidationCount, 'From "Global" HDInsight Management Endpoint IP #' + str(globalIPIndex) + " " + str(HDIME_IP) + " to subnet", "nw", "False", str(HDIME_IP), "TCP", 443, "inbound", 0))
            if self.params["DEBUG_ONLY_FIRST_HDIME_VALIDATION"] == "True":
                break  # Only 1st is enough for dev

        # Add "Regional" HDInsight Management Endpoint (HDIME) validations
        regionalIPIndex = 0
        for HDIME_IP in self.CURRENT_REGION_HDIME_IPS:
            regionalIPIndex = regionalIPIndex + 1
            self.totalValidationCount = self.totalValidationCount + 1
            self.validations.append(Validation(self.totalValidationCount, 'From "Regional" HDInsight Management Endpoint IP #' + str(regionalIPIndex) + " " + str(HDIME_IP) + " to subnet", "nw", "False", str(HDIME_IP), "TCP", 443, "inbound", 0))
            if self.params["DEBUG_ONLY_FIRST_HDIME_VALIDATION"] == "True":
                break  # Only 1st is enough for dev

        numberOfValidationsToBeExecuted = 0
        for v in self.validations:
            numberOfValidationsToBeExecuted = numberOfValidationsToBeExecuted + 1

        showTextWithIcon(self, str(numberOfValidationsToBeExecuted) + " connection checks calculated and added to the list", "line", "info")

        printAndLog(self, "")
        printAndLog(self, "---------------------------------------------------------------")
        printAndLog(self, Fore.CYAN + "C) Execution of connection checks ...                          ")
        printAndLog(self, "---------------------------------------------------------------")

        # --------MAIN MENU---------------
        which_validations = ""
        # if self.verboseMode:
        printAndLog(self, "Which connection checks you want to make ? : ")
        printAndLog(self, '1 - All connection checks (default, just press "Enter")')
        printAndLog(self, "2 - Outbound connection checks only")
        printAndLog(self, "3 - Inbound connection checks only")
        which_validations = input()
        if which_validations == "":
            which_validations = "1"

        # which_validations = "3"

        if which_validations == "1":
            for v in self.validations:
                v.active = True

        if which_validations == "2":
            for v in self.validations:
                if v.direction == "outbound":
                    v.active = True

        if which_validations == "3":
            for v in self.validations:
                if v.direction == "inbound":
                    v.active = True

        self.logger.info("User selected " + which_validations)

        # (B) Add INBOUND validations to the dictionary (Validations from HDInsight Management Endpoint IP addresses)
        if which_validations == "1" or which_validations == "3":

            # VerifyIPFlow
            # https://docs.microsoft.com/en-us/python/api/azure-mgmt-network/azure.mgmt.network.v2020_06_01.aio.operations.networkwatchersoperations?view=azure-python#begin-verify-ip-flow-resource-group-name--str--network-watcher-name--str--parameters--azure-mgmt-network-v2020-06-01-models--models-py3-verificationipflowparameters----kwargs-----azure-core-polling--async-poller-asynclropoller--forwardref--models-verificationipflowresult---
            # https://github.com/Azure/azure-sdk-for-python/blob/azure-mgmt-network_18.0.0/sdk/network/azure-mgmt-network/tests/test_cli_mgmt_network_watcher.py

            vifParams = {
                "target_resource_id": "/subscriptions/" + self.subscription_id + "/resourceGroups/" + self.current_vm_rg.name + "/providers/Microsoft.Compute/virtualMachines/" + self.current_vm.name + "",
                "direction": "Inbound",
                "protocol": "TCP",
                "local_port": "22",
                "remote_port": "*",
                "local_ip_address": self.current_vm_ip,
                "remote_ip_address": "8.8.8.8",
            }

    def doValidations(self):
        """Execute the validations"""
        numberOfValidationsToBeExecuted = 0
        for v in self.validations:
            if v.active == True:
                numberOfValidationsToBeExecuted = numberOfValidationsToBeExecuted + 1

        printAndLog(self, "\n")
        print("")
        # printAndLog(self, "-------------------------------")
        # printAndLog(self, "Executing connection checks ...")
        # printAndLog(self, "-------------------------------")

        printAndLog(
            self,
            str(numberOfValidationsToBeExecuted) + " out of " + str(len(self.validations)) + " connection checks will be done",
        )

        printAndLog(self, "Starting connection checks....")

        for v in self.validations:

            spinner = Halo(text="Checking", spinner="line", placement="left")

            if v.active == True:
                printAndLog(self, "Connection check #" + str(v.id) + " - " + v.name)
                if self.verboseMode:
                    if v.direction == "outbound":
                        printAndLog(self, 'Trying to access "' + Fore.GREEN + v.hostname + " " + v.protocol + " " + str(v.port) + Style.RESET_ALL + '" within ' + str(v.timeout) + "s timeout period...")
                        printAndLog(self, "Direction : " + Fore.GREEN + "Outbound" + Style.RESET_ALL)
                    else:
                        printAndLog(self, 'Check access from "' + Fore.GREEN + v.hostname + " " + v.protocol + " " + str(v.port) + Style.RESET_ALL + '" to subnet')
                        printAndLog(self, "Direction : " + Fore.GREEN + "Inbound" + Style.RESET_ALL)

                # if self.verboseMode:
                #     v = doValidation(self, v, True)
                # else:
                #     v = doValidation(self, v, False)

                spinner.start()
                v = doValidation(self, v, True)

                if v.succeeded:
                    spinner.text = "Result : " + Fore.GREEN + "Success" + Style.RESET_ALL
                    spinner.succeed()
                    if self.verboseMode:
                        printAndLog(self, "CmdOut : " + v.cmdout)
                else:
                    spinner.text = "Result : " + Fore.RED + "Failure" + Style.RESET_ALL
                    spinner.fail()
                    self.failedValidationCount = self.failedValidationCount + 1
                    printAndLog(self, Fore.RED + "Error : " + v.cmdout + Style.RESET_ALL)
                printAndLog(self, "")

                spinner.stop()

    def showResult(self):
        """Show the result"""
        if self.failedValidationCount > 0:
            printAndLog(self, "\n")
            printAndLog(self, "============================================================RESULT==========================================================================")
            # printAndLog(
            #     self,
            #     str(self.failedValidationCount) + " connection checks out of total " + str(len(self.validations)) + " below are failed : \n",
            # )
            showTextWithIcon(self, Fore.RED + " Below " + str(self.failedValidationCount) + " connection checks out of total " + str(len(self.validations)) + " are failed :(", "line", "result_fail")

            for v in self.validations:
                if v.active and not (v.succeeded):
                    printAndLog(self, "#" + str(v.id) + " - " + v.name)
                    printAndLog(
                        self,
                        'Host: "' + v.hostname + '"' + " , Protocol: " + v.protocol + " , Port: " + str(v.port),
                    )
                    if v.direction == "outbound":
                        printAndLog(self, 'Action required : Check your NSG/UDR/Firewall to see if you are allowing traffic to those hosts/ports in "Outbound" direction')
                    else:
                        printAndLog(self, 'Action required : Check your NSG/UDR/Firewall to see if you are allowing traffic to those hosts/ports in "Inbound" direction')
                    printAndLog(self, "")

            printAndLog(
                self,
                "============================================================================================================================================",
            )
        else:
            printAndLog(self, "\n")
            printAndLog(
                self,
                "===============RESULT================================================\n",
            )

            if self.hdinsight_cluster != None:
                showTextWithIcon(self, Fore.GREEN + "SUCCESS: Your networking settings looks ok for you to use your '" + self.params["CLUSTER_DNS_NAME"] + "' HDInsight cluster :)", "line", "result_success")
            else:
                showTextWithIcon(self, Fore.GREEN + "SUCCESS: You can create your HDInsight cluster in this VNet/Subnet :)", "line", "result_success")
            printAndLog(self, "===============RESULT================================================")

    def doCleanup(self):
        """do the cleanup"""
        if "HDInsightDiagNW-" in str(self.current_nw.name):
            cleanupAnswer = input('This tool needed to create an Azure Network Watcher resource named "' + str(self.current_nw.name) + '" to do some of the checks above. Do you want me to delete this Azure Network Watcher (y)/n ? ')
            printAndLog(self, 'You may enter "n" if you are going to rerun this tool. So the script won\'t lose time, around 10 seconds, next time')
            if cleanupAnswer == "y" or cleanupAnswer == "":
                self.logger.info("User selected YES")
                deleteNetworkWatcher(self)
            else:
                self.logger.info("User selected NO")


hnv = HDInsightNetworkValidator()
if len(sys.argv) > 1:
    if sys.argv[1] == "-v":
        # verbose mode
        hnv.verboseMode = True
hnv.main()
