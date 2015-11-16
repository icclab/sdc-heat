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

__author__ = 'ernm'


from sdcadmin.datacenter import DataCenter

import uuid
from ConfigParser import SafeConfigParser

from heat.engine import properties
from heat.engine import resource
from heat.common.i18n import _
from oslo_log import log as logging

logger = logging.getLogger(__name__)

#TODO: improve cfg-loading
SDC_CONFIG_FILE = '/opt/heat/plugins/sdc_plugin.conf'
#SDC_CONFIG_FILE = '/usr/lib/heat/sdc_plugin.conf'

cfg_parser = SafeConfigParser()
cfg_parser.read(SDC_CONFIG_FILE)

if cfg_parser.get('OVERRIDE', 'override_nic_tag') == 'True':
    override_nic_tag = True
    override_nic_tag_name = cfg_parser.get('OVERRIDE', 'override_nic_tag_name')
else:
    override_nic_tag = False

if cfg_parser.get('OVERRIDE', 'override_owner') == 'True':
    override_owner = True
    override_owner_uuid = cfg_parser.get('OVERRIDE', 'override_owner_uuid')
else:
    override_owner = False

if cfg_parser.get('OVERRIDE', 'real_owner') == 'True':
    real_owner = True
else:
    real_owner = False


if cfg_parser.get('OVERRIDE', 'override_endpoints') == 'True':
    override_endpoints = True
    override_sapi_endpoint = cfg_parser.get('OVERRIDE', 'override_sapi_endpoint')
    override_vmapi_endpoint = cfg_parser.get('OVERRIDE', 'override_vmapi_endpoint')
else:
    override_endpoints = False


class SDCNetwork(resource.Resource):

    PROPERTIES = (SAPI_ENDPOINT, VMAPI_ENDPOINT, OWNER_UUIDS, NAME, SUBNET, PROVISION_START, PROVISION_END, NIC_TAG, GATEWAY, VLAN,
                  RESOLVERS, ROUTES, DESCRIPTION) = \
        ('sapi_endpoint', 'vmapi_endpoint', 'owner_uuids', 'name', 'subnet', 'provision_start', 'provision_end', 'nic_tag', 'gateway',
         'vlan', 'resolvers', 'routes', 'description')

    properties_schema = {
        NAME: properties.Schema(
            properties.Schema.STRING,
            _('The network name.'),
            required=True
        ),
        SUBNET: properties.Schema(
            properties.Schema.STRING,
            _('CIDR notation of the new network'),
            required=True
        ),

        PROVISION_START: properties.Schema(
            properties.Schema.STRING,
            _('Provisioning range start IP'),
            required=True
        ),

        PROVISION_END: properties.Schema(
            properties.Schema.STRING,
            _('Provisioning range end IP'),
            required=True
        ),
        NIC_TAG: properties.Schema(
            properties.Schema.STRING,
            _('NIC Tag for the new network.'),
            required=not override_nic_tag,
            default='customer'
        ),
        GATEWAY: properties.Schema(
            properties.Schema.STRING,
            _('Gateway for the new network.'),
            required=False,
            default=''
        ),
        VLAN: properties.Schema(
            properties.Schema.INTEGER,
            _('VLAN for the new network'),
            required=False,
            default=0
        ),
        RESOLVERS: properties.Schema(
            properties.Schema.STRING,
            _('DNS servers for the new network, comma separated.'),
            required=False,
            default=''
        ),
        ROUTES: properties.Schema(
            properties.Schema.STRING,
            _('Routes for the new network, dest:via pairs, comma separated'),
            required=False,
            default=''
        ),
        DESCRIPTION: properties.Schema(
            properties.Schema.STRING,
            _('Description for the new network.'),
            required=False,
            default=''
        )
    }
    if not override_endpoints:
        properties_schema.update({
            SAPI_ENDPOINT: properties.Schema(
            properties.Schema.STRING,
            _('The URL for the RESTful Service API.'),
            required = True
            ),
            VMAPI_ENDPOINT: properties.Schema(
                properties.Schema.STRING,
                _('The URL for the RESTful VM API.'),
                required = True
            )
        })
    if not override_owner:
        properties_schema.update({
            OWNER_UUIDS: properties.Schema(
                properties.Schema.STRING,
                _('UUIDs of the new network, comma separated.'),
                required=not override_owner
            )
        })

    attributes_schema = {
        'uuid': _('uuid')
    }

    def _get_dc(self):
        if override_endpoints:
            sapi_endpoint = override_sapi_endpoint
            vmapi_endpoint = override_vmapi_endpoint
        else:
            sapi_endpoint = self.properties.get(self.SAPI_ENDPOINT)
            vmapi_endpoint = self.properties.get(self.VMAPI_ENDPOINT)



        dc = DataCenter(sapi=sapi_endpoint, vmapi=vmapi_endpoint)
        # TODO: add grace period, i.e. retries=3
        # if dc.healthcheck_vmapi() != True:
        #     raise Exception('VMAPI not healthy')
        return dc

    def _resolve_attribute(self, name):

        dc = self._get_dc()
        logger.debug("lookup for %s, resource_id: %s" % (name, self.resource_id))
        network = dc.get_network(self.resource_id)
        logger.debug("network: %s" % network)
        if network:
            return getattr(network, name)

    def handle_create(self):

        dc = self._get_dc()

        sapi_endpoint = self.properties.get(self.SAPI_ENDPOINT)
        if override_owner:
            owner_uuids = override_owner_uuid
        else:
            owner_uuids = self.properties.get(self.OWNER_UUIDS)
        name = self.properties.get(self.NAME)
        subnet = self.properties.get(self.SUBNET)
        provision_start = self.properties.get(self.PROVISION_START)
        provision_end = self.properties.get(self.PROVISION_END)

        if override_nic_tag:
            nic_tag = override_nic_tag_name
        else:
            nic_tag = self.properties.get(self.NIC_TAG)
        gateway = self.properties.get(self.GATEWAY)
        vlan = self.properties.get(self.VLAN)
        resolvers = self.properties.get(self.RESOLVERS).split(',')
        routes = self.properties.get(self.ROUTES)
        tupel_obj = {}
        for tupel in routes.split(','):
            k, v = tupel.split(':')
            tupel_obj[k] = v
        routes = tupel_obj
        description = self.properties.get(self.DESCRIPTION)

        logger.debug(_("Trying to create a Network with "
                       "sapi_endpoint: %s, "
                       "owner_uuids: %s, "
                       "name: %s, "
                       "subnet: %s, "
                       "provision_start: %s, "
                       "provision_end: %s, "
                       "nic_tag: %s, "
                       "gateway: %s, "
                       "vlan: %s, "
                       "resolvers: %s, "
                       "routes: %s, "
                       "description: %s") % (sapi_endpoint, owner_uuids, name, subnet, provision_start, provision_end,
                                         nic_tag, gateway, vlan, resolvers, routes, description))
        network = dc.create_network(name, owner_uuids, subnet, provision_start, provision_end, nic_tag, gateway, vlan,
                                    resolvers, routes,  description)

        logger.debug(_("Network created %s") % network)

        self.resource_id_set(network.uuid)

        return network.uuid


    def handle_delete(self):
        logger.debug(_("Delete network %s") % self.resource_id)

        dc = self._get_dc()

        # enables to delete a stack if it was not created successfully, e.a. no resource_id
        if self.resource_id is None:
            logger.debug(_("Delete: resource_id is empty - nothing to do, exiting."))
            return

        network = dc.get_network(self.resource_id)

        if network == None:
            return True

        network.delete()


class SDCSmartNetwork(SDCNetwork):

    PROPERTIES = (SAPI_ENDPOINT, VMAPI_ENDPOINT, OWNER_UUIDS, NAME, MASK_BITS, DESCRIPTION) = \
        ('sapi_endpoint', 'vmapi_endpoint', 'owner_uuids', 'name', 'mask_bits', 'description')

    properties_schema = {
        NAME: properties.Schema(
            properties.Schema.STRING,
            _('The network name.'),
            required=True
        ),

        MASK_BITS: properties.Schema(
            properties.Schema.NUMBER,
            _('Number of Bits in the Netmask'),
            required=False,
            default=24
        ),

        DESCRIPTION: properties.Schema(
            properties.Schema.STRING,
            _('Description for the new network.'),
            required=False,
            default=''
        )
    }
    if not override_endpoints:
        properties_schema.update({
            SAPI_ENDPOINT: properties.Schema(
            properties.Schema.STRING,
            _('The URL for the RESTful Service API.'),
            required = True
            ),
            VMAPI_ENDPOINT: properties.Schema(
                properties.Schema.STRING,
                _('The URL for the RESTful VM API.'),
                required = True
            )
        })
    if not override_owner:
        properties_schema.update({
            OWNER_UUIDS: properties.Schema(
                properties.Schema.STRING,
                _('UUIDs of the new network, comma separated.'),
                required=not override_owner
            )
        })

    def handle_create(self):

        dc = self._get_dc()



        sapi_endpoint = self.properties.get(self.SAPI_ENDPOINT)
        if override_owner:
            if real_owner:
                owner_uuids = self.keystone()._client.user_id
            else:
                owner_uuids = override_owner_uuid
        else:
            owner_uuids = self.properties.get(self.OWNER_UUIDS)
        name = self.properties.get(self.NAME) + '.' + uuid.uuid4().__str__()
        mask_bits = self.properties.get(self.MASK_BITS)
        description = self.properties.get(self.DESCRIPTION)

        logger.debug(_("Trying to create a Network with "
                       "sapi_endpoint: %s, "
                       "owner_uuids: %s, "
                       "name: %s, "
                       "mask_bits: %s, "
                       "description: %s") % (sapi_endpoint, owner_uuids, name, mask_bits, description))
        network = dc.create_smart_network(name, owner_uuids, mask_bits=mask_bits, description=description)

        logger.debug(_("Network created %s") % network)

        self.resource_id_set(network.uuid)

        return network.uuid


class SDCMachine(resource.Resource):
    PROPERTIES = (SAPI_ENDPOINT, VMAPI_ENDPOINT,  USER_UUID, INSTANCE_ALIAS, PACKAGE, IMAGE, NETWORKS, USER_SCRIPT) = \
        ('sapi_endpoint', 'vmapi_endpoint', 'user_uuid', 'instance_alias', 'package', 'image', 'networks', 'user_script')

    properties_schema = {
        INSTANCE_ALIAS: properties.Schema(
            properties.Schema.STRING,
            _('The instance name.'),
            required=False,
            default=''
        ),
        PACKAGE: properties.Schema(
            properties.Schema.STRING,
            _('Package UUID to use'),
            required=True
        ),

        IMAGE: properties.Schema(
            properties.Schema.STRING,
            _('Image UUID to use'),
            required=True
        ),

        NETWORKS: properties.Schema(
            properties.Schema.STRING,
            _('The Network UUID.'),
            required=True
        ),
        USER_SCRIPT: properties.Schema(
            properties.Schema.STRING,
            _('The user script.'),
            required=False,
            default='',
            update_allowed=True
        )

    }

    if not override_endpoints:
        properties_schema.update({
            SAPI_ENDPOINT: properties.Schema(
            properties.Schema.STRING,
            _('The URL for the RESTful Service API.'),
            required = True
            ),
            VMAPI_ENDPOINT: properties.Schema(
                properties.Schema.STRING,
                _('The URL for the RESTful VM API.'),
                required = True
            )
        })
    if not override_owner:
        properties_schema.update({
            USER_UUID: properties.Schema(
                properties.Schema.STRING,
                _('User UUID.'),
                required=True
            )
        })

    def _get_dc(self):
        if override_endpoints:
            sapi_endpoint = override_sapi_endpoint
            vmapi_endpoint = override_vmapi_endpoint
        else:
            sapi_endpoint = self.properties.get(self.SAPI_ENDPOINT)
            vmapi_endpoint = self.properties.get(self.VMAPI_ENDPOINT)



        dc = DataCenter(sapi=sapi_endpoint, vmapi=vmapi_endpoint)
        # TODO: add grace period, i.e. retries=3
        # if dc.healthcheck_vmapi() != True:
        #     raise Exception('VMAPI not healthy')
        return dc

    def _resolve_attribute(self, name):

        dc = self._get_dc()

        machine = dc.get_machine(self.resource_id)
        if machine:
            if name == 'network_ip':
                return machine.nics[0].get('ip')
            if name == 'external_ip':
                try:
                    return ','.join([nic.get('ip') for nic in machine.nics if nic.get('nic_tag') == 'external'])
                except:
                    return ''
            if name == 'internal_ip':
                 try:
                    return ','.join([nic.get('ip') for nic in machine.nics if nic.get('nic_tag') == 'customer'])
                 except:
                    return ''
            return getattr(machine, name)

    attributes_schema = {
        'network_ip': _('ip address'),
        'external_ip': _('external ip address'),
        'internal_ip': _('internal ip address')
    }

    # def handle_create(self): <- is handled in SDCSmartMachine and SDCKVM

    def check_create_complete(self, _compute_id):

        dc = self._get_dc()

        logger.debug(_("Check create server %s") % self.resource_id)
        machine = dc.get_machine(self.resource_id)
        return machine.is_running()

    def handle_suspend(self):
        logger.debug(_("suspend server %s") % self.resource_id)

        dc = self._get_dc()

        # enables to delete a stack if it was not created successfully, e.a. no resource_id
        if self.resource_id is None:
            logger.debug(_("Suspend: resource_id is empty - nothing to do, exiting."))
            return

        instance = dc.get_machine(self.resource_id)

        instance.stop()

    def check_suspend_complete(self, _compute_id):
        dc = self._get_dc()

        logger.debug(_("Check suspend server %s") % self.resource_id)
        machine = dc.get_machine(self.resource_id)
        return machine.is_stopped()

    def handle_resume(self):
        logger.debug(_("resume server %s") % self.resource_id)

        dc = self._get_dc()

        # enables to delete a stack if it was not created successfully, e.a. no resource_id
        if self.resource_id is None:
            logger.debug(_("Resume: resource_id is empty - nothing to do, exiting."))
            return

        instance = dc.get_machine(self.resource_id)

        instance.start()

    def check_resume_complete(self, _compute_id):
        dc = self._get_dc()

        logger.debug(_("Check resuming server %s") % self.resource_id)
        machine = dc.get_machine(self.resource_id)
        return machine.is_running()

    def handle_delete(self):
        logger.debug(_("Delete server %s") % self.resource_id)
        dc = self._get_dc()

        # enables to delete a stack if it was not created successfully, e.a. no resource_id
        if self.resource_id is None:
            logger.debug(_("Delete: resource_id is empty - nothing to do, exiting."))
            return

        logger.debug("Deleting machine with id %s" % self.resource_id)
        instance = dc.get_machine(self.resource_id)

        instance.delete()

    def check_delete_complete(self, _compute_id):
        dc = self._get_dc()

        logger.debug(_("Check delete server %s") % self.resource_id)
        if self.resource_id is None:
            logger.debug(_("Delete: resource_id is empty - nothing to do, exiting."))
            return True
        machine = dc.get_machine(self.resource_id)
        return machine.is_destroyed()

    def handle_update(self, json_snippet=None, tmpl_diff=None, prop_diff=None):

        dc = self._get_dc()

        logger.debug(_("Update server %s") % self.resource_id)
        logger.debug("json_snippet: %s" % json_snippet)
        logger.debug("tmpl_diff: %s" % tmpl_diff)
        logger.debug("prop_diff: %s" % prop_diff)

        if self.USER_SCRIPT in prop_diff:
            new_user_script = prop_diff[self.USER_SCRIPT]
            machine = dc.get_machine(self.resource_id)
            logger.debug('Update server %s with new user-script: %s' % (self.resource_id, new_user_script))
            customer_metadata = machine.customer_metadata
            customer_metadata.update({'user-script': new_user_script, 'rerun-user-script': 'True'})
            machine.update_metadata('customer_metadata', customer_metadata)
            return customer_metadata
        return None

    def check_update_complete(self, token):
        dc = self._get_dc()
        logger.debug(_("Check if update is complete"))
        machine = dc.get_machine(self.resource_id)
        if token.get('user-script') == machine.customer_metadata.get('user-script'):
            logger.debug(_("user-script updated"))
            return True
        logger.debug(_("user-script not yet updated"))
        return False


class SDCSmartMachine(SDCMachine):

    def handle_create(self):

        dc = self._get_dc()

        if override_owner:
            if real_owner:
                user_uuid = self.keystone()._client.user_id
            else:
                user_uuid = override_owner_uuid
        else:
            user_uuid = self.properties.get(self.USER_UUID)
        networks = self.properties.get(self.NETWORKS).split(',')
        package = self.properties.get(self.PACKAGE)
        image = self.properties.get(self.IMAGE)
        alias = self.properties.get(self.INSTANCE_ALIAS)
        user_script = self.properties.get(self.USER_SCRIPT)

        ssh_keys = False
        if not real_owner:
            ssh_keys = []
            try:
                for key in self.nova().keypairs.list():
                    ssh_keys.append(key.public_key)
            except:
                pass
            if len(ssh_keys) == 0:
                    ssh_keys = False

        if alias:
            # add stack id to avoid alias collisions
            alias = alias + '-' + self.stack.id
        if not alias:
            alias = uuid.uuid4().__str__() + '-' + self.stack.id

        logger.debug(_("Trying to create a Machine with "
                       "owner: %s, "
                       "networks: %s, "
                       "package: %s, "
                       "image: %s, "
                       "alias: %s, "
                       "user_script.__len__(): %i,"
                       "ssh_keys: %s") % (user_uuid, networks.__str__(), package, image, alias,
                                                       user_script.__len__(), ssh_keys))
        machine = dc.create_smart_machine(owner=user_uuid,
                                          networks=networks,
                                          package=package,
                                          image=image,
                                          alias=alias,
                                          user_script=user_script,
                                          inject_rerunnable_userscript_functionality=True,
                                          ssh_keys=ssh_keys)
        logger.debug(_("VM Created %s") % machine)

        self.resource_id_set(machine.uuid)

        return machine.uuid


class SDCKVM(SDCMachine):

    def handle_create(self):

        dc = self._get_dc()

        if override_owner:
            user_uuid = override_owner_uuid
        else:
            user_uuid = self.properties.get(self.USER_UUID)
        networks = self.properties.get(self.NETWORKS).split(',')
        package = self.properties.get(self.PACKAGE)
        image = self.properties.get(self.IMAGE)
        alias = self.properties.get(self.INSTANCE_ALIAS)
        user_script = self.properties.get(self.USER_SCRIPT)

        ssh_keys = False
        if not real_owner:
            ssh_keys = []
            try:
                for key in self.nova().keypairs.list():
                    ssh_keys.append(key.public_key)
            except:
                pass
            if len(ssh_keys) == 0:
                    ssh_keys = False

        if alias:
            # add stack id to avoid alias collisions
            alias = alias + '-' + self.stack.id
        if not alias:
            alias = uuid.uuid4().__str__() + '-' + self.stack.id

        logger.debug(_("Trying to create a Machine with "
                       "owner: %s, "
                       "networks: %s, "
                       "package: %s, "
                       "image: %s, "
                       "alias: %s, "
                       "user_script.__len__(): %i,"
                       "ssh_keys: %s") % (user_uuid, networks.__str__(), package, image, alias,
                                                       user_script.__len__(), ssh_keys))
        machine = dc.create_kvm_machine(owner=user_uuid,
                                        networks=networks,
                                        package=package,
                                        image=image,
                                        alias=alias,
                                        user_script=user_script,
                                        inject_rerunnable_userscript_functionality=True,
                                        ssh_keys=ssh_keys)
        logger.debug(_("VM Created %s") % machine)

        self.resource_id_set(machine.uuid)

        return machine.uuid


def resource_mapping():
    cfg_parser = SafeConfigParser()
    cfg_parser.read(SDC_CONFIG_FILE)

    enable_smartmachine = cfg_parser.get('RESOURCES', 'enable_smartmachine')
    enable_kvm = cfg_parser.get('RESOURCES', 'enable_kvm')
    enable_network = cfg_parser.get('RESOURCES', 'enable_network')
    enable_smart_network = cfg_parser.get('RESOURCES', 'enable_smart_network')

    mappings = {}

    if enable_smartmachine == 'True':
        mappings['SDC::Compute::SmartMachine'] = SDCSmartMachine
    if enable_kvm == 'True':
        mappings['SDC::Compute::KVM'] = SDCKVM
    if enable_network == 'True':
        mappings['SDC::Network::Network'] = SDCNetwork
    if enable_smart_network == 'True':
        mappings['SDC::Network::SmartNetwork'] = SDCSmartNetwork

    return mappings