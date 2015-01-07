# Copyright 2014 Zuercher Hochschule fuer Angewandte Wissenschaften
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

from heat.engine import properties
from heat.engine import resource
from heat.openstack.common.gettextutils import _
from heat.openstack.common import log as logging

logger = logging.getLogger(__name__)


class SDCMachine(resource.Resource):
    PROPERTIES = (SAPI_ENDPOINT, USER_UUID, INSTANCE_ALIAS, PACKAGE, IMAGE, NETWORKS, USER_SCRIPT) = \
        ('sapi_endpoint', 'user_uuid', 'instance_alias', 'package', 'image', 'networks', 'user_script')

    properties_schema = {

        SAPI_ENDPOINT: properties.Schema(
            properties.Schema.STRING,
            _('The URL for the RESTful Service API.'),
            required=True
        ),

        USER_UUID: properties.Schema(
            properties.Schema.STRING,
            _('The username in the CloudSigma Cloud.'),
            required=True
        ),

        INSTANCE_ALIAS: properties.Schema(
            properties.Schema.STRING,
            _('The instance name.'),
            required=False,
            default=''
        ),
        PACKAGE: properties.Schema(
            properties.Schema.STRING,
            _('Package UUID to use'),
            required=True,
            default=256
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
            default=''
        )

    }

    def _resolve_attribute(self, name):

        dc = self._get_dc()

        machine = dc.get_machine(self.resource_id)
        if machine:
            if name == 'network_ip':
                return machine.nics[0].get('ip')
            return getattr(machine, name)

    attributes_schema = {
        'network_ip': _('ip address')
    }

    def _get_dc(self):
        dc = DataCenter(sapi=self.properties.get(self.SAPI_ENDPOINT))
        # TODO: add grace period, i.e. retries=3
        # if dc.healthcheck_vmapi() != True:
        #     raise Exception('VMAPI not healthy')
        return dc

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

        instance = dc.get_machine(self.resource_id)

        instance.delete()

    def check_delete_complete(self, _compute_id):

        dc = self._get_dc()

        logger.debug(_("Check delete server %s") % self.resource_id)
        machine = dc.get_machine(self.resource_id)
        return machine.is_destroyed()


class SDCSmartMachine(SDCMachine):

    def handle_create(self):

        dc = self._get_dc()

        user_uuid = self.properties.get(self.USER_UUID)
        networks = [self.properties.get(self.NETWORKS)]
        package = self.properties.get(self.PACKAGE)
        image = self.properties.get(self.IMAGE)
        alias = self.properties.get(self.INSTANCE_ALIAS)
        user_script = self.properties.get(self.USER_SCRIPT)

        if not alias:
            alias = uuid.uuid4().__str__()

        logger.debug(_("Trying to create a Machine with "
                       "owner: %s, "
                       "networks: %s, "
                       "package: %s, "
                       "image: %s, "
                       "alias: %s, "
                       "user_script.__len__(): %i") % (user_uuid, networks.__str__(), package, image, alias,
                                                       user_script.__len__()))
        machine = dc.create_smart_machine(owner=user_uuid,
                                          networks=networks,
                                          package=package,
                                          image=image,
                                          alias=alias,
                                          user_script=user_script)
        logger.debug(_("VM Created %s") % machine)

        self.resource_id_set(machine.uuid)

        return machine.uuid


class SDCKVM(SDCMachine):

    def handle_create(self):

        dc = self._get_dc()

        user_uuid = self.properties.get(self.USER_UUID)
        networks = [self.properties.get(self.NETWORKS)]
        package = self.properties.get(self.PACKAGE)
        image = self.properties.get(self.IMAGE)
        alias = self.properties.get(self.INSTANCE_ALIAS)
        user_script = self.properties.get(self.USER_SCRIPT)

        if not alias:
            alias = uuid.uuid4().__str__()

        logger.debug(_("Trying to create a Machine with "
                       "owner: %s, "
                       "networks: %s, "
                       "package: %s, "
                       "image: %s, "
                       "alias: %s, "
                       "user_script.__len__(): %i") % (user_uuid, networks.__str__(), package, image, alias,
                                                       user_script.__len__()))
        machine = dc.create_kvm_machine(owner=user_uuid, networks=networks, package=package, image=image, alias=alias,
                                        user_script=user_script)
        logger.debug(_("VM Created %s") % machine)

        self.resource_id_set(machine.uuid)

        return machine.uuid


def resource_mapping():
    return {
        'SDC::Compute::SmartMachine': SDCSmartMachine,
        'SDC::Compute::KVM': SDCKVM
    }