import sys
import os.path
from os import path
import zipfile
import json
from pprint import pprint

class ARMRequest:
    clusterName = ''
    location = ''
    clusterKind = ''
    clusterVersion = ''
    domainUsername = ''
    rangerDbServerName = ''
    rangerDbName = ''
    
    componentVersion = ''
    HiveSQLServer = ''

    HiveDatabaseName = ''
    OozieSQLServer = ''
    OozieDatabaseName = ''
    AmbariQLServer = ''
    AmbariDatabaseName = ''

    storageAccountName = ''
    msiResourceId = ''

    Vnet = ''
    Subnet = ''

    resourceProviderConnection = ''

    aaddsResourceId = ''
    domain = ''
    ldapsUrls = ''
    msiResourceIdESP = ''

if not( path.exists('template.zip')):
    print('Please put the \'template.zip\' file that you downloaded from Azure Portal into the current folder')
    sys.exit()


with zipfile.ZipFile('template.zip','r') as z:
    z.extractall('.')


ARMtemplateFilename = 'template.json'
ARMtemplateParametersFilename = 'parameters.json'

with open(ARMtemplateFilename) as template_data:
    arm = json.load(template_data)

with open(ARMtemplateParametersFilename) as parameters_data:
    params = json.load(parameters_data)

req = ARMRequest()

req.location = params['parameters']['location']['value']
req.clusterKind = params['parameters']['clusterKind']['value']
req.clusterVersion = params['parameters']['clusterVersion']['value']
req.domainUsername = params['parameters']['domainUsername']['value']
req.rangerDbServerName = params['parameters']['rangerDbServerName']['value']
req.rangerDbName = params['parameters']['rangerDbName']['value']

properties = arm['resources'][0]['properties']
clusterDefinition = properties['clusterDefinition'] 
req.componentVersion = clusterDefinition['componentVersion']
req.HiveSQLServer = clusterDefinition['configurations']['hive-env']['hive_existing_mssql_server_host']
req.HiveDatabaseName = clusterDefinition['configurations']['hive-env']['hive_existing_mssql_server_database']
req.OozieSQLServer = clusterDefinition['configurations']['oozie-env']['oozie_existing_mssql_server_host']
req.OozieDatabaseName = clusterDefinition['configurations']['oozie-env']['oozie_existing_mssql_server_database']
req.AmbariQLServer = clusterDefinition['configurations']['ambari-conf']['database-server']
req.AmbariDatabaseName = clusterDefinition['configurations']['ambari-conf']['database-name']


#TODO multiple storage accounts!
req.storageAccountName = properties['storageProfile']['storageaccounts'][0]['name']
req.msiResourceId = properties['storageProfile']['storageaccounts'][0]['msiResourceId']

req.Vnet = properties['computeProfile']['roles'][0]['virtualNetworkProfile']['id']
req.Subnet = properties['computeProfile']['roles'][0]['virtualNetworkProfile']['subnet']

req.resourceProviderConnection = properties['networkProperties']['resourceProviderConnection']

req.aaddsResourceId = properties['securityProfile']['aaddsResourceId']
req.domain = properties['securityProfile']['domain']
req.ldapsUrls = properties['securityProfile']['ldapsUrls'][0]
req.msiResourceIdESP = properties['securityProfile']['msiResourceId']

pprint(vars(req))
