from lib.utils import printAndLog
import sys

from azure.identity import DefaultAzureCredential


def getStorageAccounts(self):
    """Get the storage accounts, either from params or from HDInsight cluster if it's already created"""

    tmpStorageAccount = ""
    if self.params["CLUSTER_DNS_NAME"] == "":
        # Get storage accounts by using the storage account names customer supplied in params.conf
        if self.params["PRIMARY_STORAGE"] != "":
            tmpStorageAccount = getStorageAccountByName(self, self.params["PRIMARY_STORAGE"])
            if tmpStorageAccount == None:
                printAndLog(self, '"' + self.params["PRIMARY_STORAGE"] + '" you have supplied with PRIMARY_STORAGE parameter does not exist in this subscription')
                sys.exit()
            else:
                self.storageAccounts.append(tmpStorageAccount)
        else:  # Customer hasn't supplied PRIMARY_STORAGE account
            return None

        if self.params["SECONDARY_STORAGE"] != "":
            tmpStorageAccount = getStorageAccountByName(self, self.params["SECONDARY_STORAGE"])
            if tmpStorageAccount == None:
                printAndLog(self, '"' + self.params["SECONDARY_STORAGE"] + '" you have supplied with SECONDARY_STORAGE parameter does not exist in this subscription')
                sys.exit()
            else:
                self.storageAccounts.append(tmpStorageAccount)

    else:  # TODO --- KAFKAAAAAAAAAAAAAAAA!

        # HDInsight cluster already created, get storage account names from 'storageProfile' of the cluster
        for storageaccount in self.hdinsight_cluster.properties.additional_properties["storageProfile"]["storageaccounts"]:
            # printAndLog(self,storageaccount['name'])
            self.storageAccounts.append(getStorageAccountByName(self, storageaccount["name"]))

    return


def getStorageAccountByName(self, storageAccountName):
    """Gets the StorageAccount object"""

    # Get all the storage accounts in the subscription
    allStorageAccounts = self.storage_client.storage_accounts.list()

    # Kind: BlobStorage ==> WASB (Example : 'https://rechappastorage.blob.core.windows.net/', dfs: 'https://rechappastorage.dfs.core.windows.net/')
    # Kind: Storage ==> WASB
    # Kind: StorageV2 and NOT(is_hns_enabled) ==> WASB
    # Kind: StorageV2 and is_hns_enabled ==> ADLSGen2

    # Because storage_client.storage_accounts.get_properties requires storage account's resource group and we don't know the rg, we are looping through all the storage accounts
    for storageAccount in allStorageAccounts:
        if (storageAccountName in str(storageAccount.primary_endpoints.blob)) or (storageAccountName in str(storageAccount.primary_endpoints.dfs)):
            return storageAccount
    return None


def checkSecureTransferRequiredIsSetForAllStorageAccounts(self):
    """Check if 'SecureTransferRequired' option is set in all storage accounts"""
    if all(storageAccount.enable_https_traffic_only == True for storageAccount in self.storageAccounts):
        return True
    return False


def isStorageFirewallEnabled(self, storageAccount):
    """Returns True if the given "storageAccount" is storage firewall enabled"""
    if storageAccount.network_rule_set.virtual_network_rules:
        return True
    return False


def noFirewallEnabledInAnyStorageAccount(self):
    """Returns True if no firewall enabled in any storage account"""

    if all((storageAccount.network_rule_set.default_action == "Allow") for storageAccount in self.storageAccounts):
        return True
    else:
        return False


def checkIfCurrentSubnetIsAllowedInAllStorageAccountsFirewallsIfEnabled(self):
    """Checks if storage account has storage firewall and current subnet is allowed"""
    for storageAccount in self.storageAccounts:
        if storageAccount.network_rule_set.virtual_network_rules:
            for virtual_network_rule in storageAccount.network_rule_set.virtual_network_rules:
                if ("virtualNetworks/" + self.current_vnet.name + "/subnets/" + self.current_subnet.name) in virtual_network_rule.virtual_network_resource_id:
                    return True
        else:
            return True
    return False
