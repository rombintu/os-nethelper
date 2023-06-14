#!/bin/python3
import sys, os
from oslo_config import cfg
from prettytable import PrettyTable
from openstack import connection

def get_nova_credentials_v2():
    creds = {}
    creds['version'] = '2'
    creds['username'] = os.environ['OS_USERNAME']
    creds['password'] = os.environ['OS_PASSWORD']
    creds['project_name'] = os.environ['OS_PROJECT_NAME']
    creds['auth_url'] = os.environ['OS_AUTH_URL']
    creds['project_domain_name'] = os.getenv('OS_PROJECT_DOMAIN_NAME', 'Default')
    creds['user_domain_name'] = os.getenv('OS_USER_DOMAIN_NAME', 'admin')
    return creds

class Network:
    def __init__(self, _id, name, is_shared):
        self._id = _id
        self.name = name
        self.is_shared = is_shared


class Project:
    def __init__(self, _id, name, quota_instances):
        self._id = _id
        self.name = name
        self.quota_instances = quota_instances

class RBACPolicy:
    def __init__(self, _id, type, target_project_id, object_id):
        self._id = _id
        self.type = type
        self.target_project_id = target_project_id
        self.object_id = object_id


class Openstack:
    networks = []
    projects = []
    rbac_policies = []

    def __init__(self):
        self.creds = get_nova_credentials_v2()
        self.conn = connection.Connection(**self.creds)
        self.get_networks()
        self.get_projects()
        self.get_rbac_policies()
        
    def get_networks(self):
        self.networks = [Network(n.id, n.name, n.is_shared) for n in self.conn.network.networks()]
    
    def get_projects(self):
        self.projects = [
            Project(p.id, p.name, self.conn.get_compute_quotas(p.id).instances) 
                for p in self.conn.identity.projects()
            ]
    def get_rbac_policies(self):
        self.rbac_policies = [
            RBACPolicy(p.id, p.object_type, p.target_project_id, p.object_id) for p in self.conn.network.rbac_policies()
        ]

if __name__ == "__main__":
    opts = [
        cfg.BoolOpt('all', default=False, help='Show all networks'),
    ]
    cli_opts = cfg.CONF
    cli_opts.register_cli_opts(opts)
    cli_opts(args=sys.argv[1:])

    os = Openstack()
    table = PrettyTable()
    table.field_names = ["Network", "CIDRs", "Total quota", "Projects"]
    networks = None
    
    if not os.networks:
        print("Not found networks")
        sys.exit(0)

    for network in os.networks:
        projects_rbac = []
        projects_name = []
        cidrs = []

        if not cli_opts.all and 'vlan' not in network.name.lower():
            continue

        for subnet in os.conn.network.subnets(network_id=network._id):
            cidrs.append(subnet.cidr)

        for rbac in os.rbac_policies:
            if rbac.object_id == network._id and rbac.type == 'network':
                projects_rbac.append(rbac.target_project_id)

        summ = 0
        for p1 in set(projects_rbac):
            if p1 == "*":
                projects_name.append("* (All projects)\n")
            for p2 in os.projects:
                if p1 == "*":
                    summ += p2.quota_instances
                if p1 == p2._id:
                    summ += p2.quota_instances
                    projects_name.append("{} (quota {})".format(p2.name, p2.quota_instances))
        table.add_row([network.name, "\n".join(cidrs), summ, "\n".join(projects_name)])
        
    print(table)