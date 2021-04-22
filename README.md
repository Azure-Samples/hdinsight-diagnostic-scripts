# Azure HDInsight Diagnostic Scripts

This project contains diagnostic scripts to assist in the creation and management of Azure HDInsight clusters.

The networkValidator.sh script can be used to ensure there is outbound connectivity from the Virtual Network (VNET) where the HDInsight cluster will be deployed to the required Azure services.

To use the script, deploy a Linux VM into the same VNET/subnet where the HDInsight cluster will be deployed. Then, download the params.txt and the networkValidator.sh scripts and save to the Linux VM. Edit the params.txt file with your resources and run the script. 
