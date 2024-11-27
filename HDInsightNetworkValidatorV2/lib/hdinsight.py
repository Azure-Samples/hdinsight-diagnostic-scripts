from lib.utils import printAndLog, showTextWithIcon
import sys
import json

def getCluster(self):
    """Get the HDInsight cluster object"""

    # Get all the HDInsight clusters
    hdinsight_clusters = self.hdinsight_client.clusters.list()

    # Get current cluster
    for hdinsight_cluster in hdinsight_clusters:
        if hdinsight_cluster.name == self.params["CLUSTER_DNS_NAME"]:
            return hdinsight_cluster
    return None


def getClusterHeadnodeIPsFromSubnet(self):
    """Get HDInsight cluster headnode IPs from subnet"""
    # Find the IP addresses of both headnodes
    headnode_ips = {}
    tmp_device_name = ""
    for ip_configuration in self.current_subnet.ip_configurations:
        tmp_device_name = ip_configuration.id.split("/")[8]

        if self.hdinsight_cluster.properties.cluster_id in tmp_device_name:
            if "-headnode-0" in tmp_device_name:
                headnode_ips["hn0"] = ip_configuration.private_ip_address
            elif "-headnode-1" in tmp_device_name:
                headnode_ips["hn1"] = ip_configuration.private_ip_address
    return headnode_ips
    
def getClusterDetailsUsingSSH(self):
    return None
