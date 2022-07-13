# HDInsight Pre-deployment Network Configuration Checks Tool (aka HNV v1)

## Instructions
1. In the same subnet that you are planning to create your HDInsight cluster, create an Azure Ubuntu 18.04 Linux VM in B1s VM size (1 vCPU, 1G RAM) or better.
2. SSH into your VM.
3. Copy all the files from this repo into any folder with the command below:

    `wget -i https://raw.githubusercontent.com/Azure-Samples/hdinsight-diagnostic-scripts/main/HDInsightNetworkValidator/all.txt`

4. Edit "params.txt" file with a text editor.
5. Run `sudo chmod +x ./setup.sh` to make setup.sh executable and run it with `sudo ./setup.sh` to install pip for Python 2.x and install the required Python 2.x modules.
6. Run the main script with `sudo python2 ./networkValidator.py`.
