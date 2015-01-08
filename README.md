# OpenStack Heat for SDC
## Step 1 - Create KVM-VM for OpenStack Services
Create a KVM-VM with the following Parameters:

* Owner: admin (the owner of the admin network)
* 4GB Ram, 2 CPU, 2000 LWPs, 40 GB Disk (create a Package if necessary)
* centos-7 Image (20141202, b1df4936-7a5c-11e4-98ed-dfe1fa3a813a)
* Primary NIC to network with internet-access (Public)
* Secondary NIC to admin network

## Step 2 - Installing Packstack
SSH as root into the machine once provisioned:

```
yum update -y
yum install -y https://rdo.fedorapeople.org/rdo-release.rpm
yum install -y openstack-packstack
```

## Step 3 - Install OpenStack Components
Generate a new answer file:

```
packstack --gen-answer-file=/root/packstack-answers
```

Modify the following lines:

```
CONFIG_GLANCE_INSTALL=n
CONFIG_CINDER_INSTALL=n
CONFIG_NOVA_INSTALL=n
CONFIG_NEUTRON_INSTALL=n
CONFIG_HORIZON_INSTALL=n
CONFIG_SWIFT_INSTALL=n
CONFIG_CEILOMETER_INSTALL=n
CONFIG_HEAT_INSTALL=y
CONFIG_NAGIOS_INSTALL=n
CONFIG_CINDER_VOLUMES_CREATE=n
CONFIG_PROVISION_DEMO=n
```

Run packstack with the modified file:

```
packstack --answer-file=/root/packstack-answers

```
This may take a while, consider having a coffee ;-)

## Step 4 - Verify OpenStack Components
Source the Creds file at ```/root/keystonerc_admin``` and run a couple of keystone and heat commands:

```
$ keystone user-list
$ heat stack-list
```

## Step 5 - Install sdcadmin library & Heat plugin
Copy the lib to ```/usr/lib/python2.7/site-packages/sdcadmin```
Symlink the heat plugin:

```
mkdir -p /usr/lib/heat
ln -s /usr/lib/python2.7/site-packages/sdc_plugin.py /usr/lib/heat/sdc_plugin.py
```
Then restart the heat engine service:

```
service openstack-heat-engine restart
```

Run ```heat resource-type-list```, verify that ```SDC::Compute::KVM``` and ```SDC::Compute::SmartMachine``` show up.


## Step 6
Setup is complete, you now can start stacks with those resources. Example heat-templates are included in this repo.


# Licence

```
# Copyright 2015 Zuercher Hochschule fuer Angewandte Wissenschaften
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
```