from lib.utils import printAndLog, showTextWithIcon
import sys
import json
import paramiko


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
    """SSH into HDInsight cluster using hn0 and get the details by executing the 2inline' python script"""

    headnode_ip = self.cluster_headnode_ips["hn0"]

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh_client.connect(
            hostname=headnode_ip,
            username=self.params["CLUSTER_SSHUSER"],
            password=self.params["CLUSTER_SSHUSER_PASS"],
        )
    except:
        printAndLog(self, "Error connecting to your cluster headnode with SSH.\n" + "Exception : " + str(sys.exc_info()[0]) + "\n" + "Exception message : " + str(sys.exc_info()[1]) + "\n")
        printAndLog(self, "Exiting.")
        sys.exit()

    if ssh_client.get_transport().is_active():
        showTextWithIcon(self, " Successfully connected to your HDInsight cluster with SSH. OK!")

    python_script_to_execute = """
import os
import sys
#import hdinsight_common.ClusterManifestParser as ClusterManifestParser
import base64
import json
from xml.etree.ElementTree import *
import xml.etree.ElementTree as ET
#cm = ClusterManifestParser.parse_local_manifest()
#print(cm.settings)
"""
    python_script_to_execute = python_script_to_execute + "\nclusterType = '" + self.hdinsight_cluster.properties.cluster_definition.kind + "'\n"
    python_script_to_execute = (
        python_script_to_execute
        + """
def getPropertyFromXML(xmlFile, property):    
    xmlRoot = ET.parse(xmlFile)
    for e in xmlRoot.findall('.//property'):
        if e[0].text == property:
            return e[1].text

def getAmbariDBServerName():
    ambariDBServerName = ''
    f = open('/etc/ambari-server/conf/ambari.properties','r')
    for line in f:
        if ( line.startswith('server.jdbc.hostname') ) :
            ambariDBServerName = line.split('=')[1]
    f.close()
    return ambariDBServerName

# def isESP():
#     isESP = 'false'
#     if os.path.exists('/etc/security/keytabs'):
#         isESP = 'true'
#     return isESP


def getLDAPuri():
    ldapURI = ''    
    f = open('/etc/ldap/ldap.conf')
    file_content = f.readlines()
    f.close()

    for line in file_content:
        #print(line)
        if 'ldaps://' in line:
            ldapURI = line.split(' ')
            for line_part in ldapURI:
                if line_part.startswith('ldaps://'):
                    ldapURI = line_part
                    break        
    return ldapURI

def getAADDSDomain():
    aadds_domain = ''
    f = open('/etc/krb5.conf','r')
    file_content = f.readlines()
    f.close()

    line_number = 0
    for line in file_content:
        line_number = line_number + 1
        if (line.startswith('[realms]')):
            aadds_domain = file_content[line_number].split('=')[0].strip(' ')
            break
    if ('ATHENA.MIT.EDU' in aadds_domain):
        aadds_domain = ''
    return aadds_domain

cluster_details = {}
####cluster_details['cluster_type'] = cm.settings['cluster_type']
####cluster_details['user_subscription_id'] = cm.settings['user_subscription_id']
####cluster_details['enable_security'] = cm.settings['enable_security']
####cluster_details['azure_db_server_name'] = cm.settings['azure_db_server_name']
#cluster_details['relay_connection_uri'] = cm.settings['relay_connection_uri']

cluster_details['ambariDBServerName'] = getAmbariDBServerName()

#isESP ?
cluster_details['aadds_domain'] = getAADDSDomain()


#Kafka!!!!!!
#####cluster_details['primaryStorageAccount'] = getPropertyFromXML('/etc/hadoop/conf/core-site.xml', 'fs.defaultFS')
if not(clusterType == 'KAFKA'):
    cluster_details['hiveDBServerName'] = getPropertyFromXML('/etc/hive/conf/hive-site.xml', 'javax.jdo.option.ConnectionURL')
    cluster_details['oozieDBServerName'] = getPropertyFromXML('/etc/oozie/conf/oozie-site.xml', 'oozie.service.JPAService.jdbc.url')

#if (cluster_details['enable_security'] == 'true'):
if (cluster_details['aadds_domain'] != ''):
    cluster_details['rangerDBServerName'] = getPropertyFromXML('/usr/hdp/current/ranger-admin/conf/ranger-admin-site.xml', 'ranger.jpa.jdbc.url')
    cluster_details['ldap_uri'] = getLDAPuri()

cluster_details_json = json.dumps(cluster_details)
print(cluster_details_json)
"""
    )

    cmd_to_execute = 'echo -e "' + python_script_to_execute + '" | sudo python2'
    stdin, stdout, stderr = ssh_client.exec_command(cmd_to_execute)

    #
    # print(stdout.readlines())
    # print(stderr.readlines())

    cmdout = ""
    for line in stdout:
        cmdout = cmdout + line.strip("\n")

    del stdin, stdout, stderr
    ssh_client.close()
    # print(cmdout)

    hdi_json = json.loads(cmdout)

    hdi_json["ambariDBServerName"] = hdi_json["ambariDBServerName"].rstrip("\n").rstrip("\\n")

    return hdi_json
