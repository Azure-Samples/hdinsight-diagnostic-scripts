#!/bin/bash
sudo apt update
sudo apt install python3-pip -y
pip3 install --upgrade pip
pip3 install netaddr --no-warn-script-location
pip3 install requests beautifulsoup4 lxml azure-identity==1.5.0 azure-mgmt-network==18.0.0 azure-mgmt-compute==20.0.0 azure-mgmt-storage==18.0.0 azure-mgmt-resource==16.1.0 msrestazure==0.6.4 azure-mgmt-hdinsight==7.0.0 halo paramiko maskpass progress colorama termcolor prettytable
#pip3 install azure-storage-blob==12.8.1 azure-storage-file-datalake==12.3.1 azure-datalake-store==0.0.51
