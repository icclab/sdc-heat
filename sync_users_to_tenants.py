#!/bin/env python

'''
Simple script that syncs users and tenants
'''

__author__ = 'ernm'

from keystoneclient.v2_0 import client
from keystoneclient.openstack.common.apiclient.exceptions import AuthorizationFailure
import argparse
import os

ROLE_NAMES_TO_GRANT = ['_member_', 'heat_stack_owner']
USER_NAMES_TO_IGNORE = ['admin', 'heat', 'keystone']


def get_client():
    '''
    creates keystone client

    read env-vars and cli arguments and constructs keystone client
    :return: keystone client
    '''
    token = os.environ.get('OS_SERVICE_TOKEN') or os.environ.get('SERVICE_TOKEN')
    endpoint = os.environ.get('OS_SERVICE_ENDPOINT') or os.environ.get('SERVICE_ENDPOINT')

    parser = argparse.ArgumentParser('sync_users_to_tenants.py')
    parser.add_argument('--os-token',
                        help='Specify an endpoint to use instead of retrieving one from '
                             'the service catalog (via authentication). Defaults to '
                             'env[OS_SERVICE_ENDPOINT].',
                        default=token,
                        dest='token')
    parser.add_argument('--os-endpoint',
                        help='Specify an existing token to use instead of retrieving one '
                             'via authentication (e.g. with username & password). '
                             'Defaults to env[OS_SERVICE_TOKEN].',
                        default=endpoint,
                        dest='endpoint')

    args = parser.parse_args()


    if not args.token or not args.endpoint:
        parser.print_help()
        exit(1)

    ks_client = client.Client(token=args.token, endpoint=args.endpoint)
    try:
        ks_client.tenants.list()

    except AuthorizationFailure:
        exit('Invalid OpenStack Identity credentials.')
    return ks_client


def get_all_tenants(ks_client):
    '''
    returns all tenants
    :param ks_client: keystone client
    :return: list of tenants
    '''
    return ks_client.tenants.list()


def get_roles_to_grant(ks_client):
    '''
    returns all roles that are to be granted
    :param ks_client: keystone client
    :return: list of roles
    '''
    roles_to_grant = [role for role in ks_client.roles.list() if role.name in ROLE_NAMES_TO_GRANT]
    assert len(ROLE_NAMES_TO_GRANT) == len(roles_to_grant), 'Unable to find all roles specified!'
    return roles_to_grant


def get_users_to_sync(ks_client):
    '''
    returns all users that are to be synced
    :param ks_client: keystone client
    :return: list of users
    '''
    users_to_check = [user for user in ks_client.users.list()
                      if user.name not in USER_NAMES_TO_IGNORE]
    assert len(users_to_check) > 0, 'No users found to sync'
    return users_to_check


def get_my_tenant(user, all_tenants):
    '''
    returns tenant with the same name as the users
    :param user: user
    :param all_tenants: list of tenants
    :return: tenant
    '''
    for tenant in all_tenants:
        if user.name == tenant.name:
            return tenant


def create_tenant(ks_client, name):
    '''
    creates a new tenant
    :param ks_client: keystone client
    :param name: name of the new tenant
    :return: tenant
    '''
    print '## creating tenant %s' % name
    my_tenant = ks_client.tenants.create(tenant_name=name, description='Tenant for user %s' % name,
                                         enabled=True)
    return my_tenant


def grant_roles_to_user(ks_client, roles, user, tenant):
    '''
    grants a list of roles to a user for a tenant
    :param ks_client: keystone client
    :param roles: roles to grant
    :param user: user to grant roles to
    :param tenant: tenant to grant roles in
    '''
    existing_roles = ks_client.roles.roles_for_user(user=user, tenant=tenant)
                # returns list of all roles which the user does not already have
    roles_to_grant = [role for role in roles if role not in existing_roles]
    for role in roles_to_grant:
        print '## grant %s to user %s in tenant %s' % (role.name, user.name, tenant.name)
        tenant.add_user(user=user, role=role)


def revoke_roles_from_user(ks_client, roles, user, tenant):
    '''
    revokes a list of roles from a user in a tenant
    :param ks_client: keystone client
    :param roles: roles to revoke
    :param user: user to revoke roles from
    :param tenant: tenant to revoke roles in
    '''
    existing_roles = ks_client.roles.roles_for_user(user=user, tenant=tenant)
    for role in [role for role in roles if role in existing_roles]:
        print '## revoke role %s from user %s in tenant %s' % (role.name, user.name, user.name)
        resp, _ = tenant.remove_user(user, role)
        resp.raise_for_status()


def disable_tenant(tenant):
    '''
    disables tenant
    :param tenant: tenant
    '''
    print '## disable tenant %s' % tenant.name
    tenant.update(enabled=False)


def sync_users_to_tenants(ks_client):
    '''
    syncs users to tenants
    :param ks_client: keystone client
    '''
    all_tenants = get_all_tenants(ks_client=ks_client)
    roles_to_grant = get_roles_to_grant(ks_client=ks_client)
    users_to_sync = get_users_to_sync(ks_client=ks_client)

    for user in users_to_sync:

        print '# syncing user %s' % user.name

        my_tenant = get_my_tenant(user, all_tenants)

        if user.enabled == u'true':
            if not my_tenant:
                my_tenant = create_tenant(ks_client=ks_client, name=user.name)
            grant_roles_to_user(ks_client=ks_client, roles=roles_to_grant, user=user,
                                tenant=my_tenant)

        else:
            if my_tenant:
                if my_tenant.enabled:
                    disable_tenant(my_tenant)
                revoke_roles_from_user(ks_client=ks_client, roles=roles_to_grant,
                                       user=user, tenant=my_tenant)


if __name__ == "__main__":
    sync_users_to_tenants(get_client())
