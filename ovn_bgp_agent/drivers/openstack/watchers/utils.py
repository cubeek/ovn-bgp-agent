# Copyright 2024 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ovn_bgp_agent import constants


def has_ip_address_defined(address):
    return ' ' in address.strip()


def get_from_external_ids(row, key):
    try:
        return row.external_ids[key]
    except (AttributeError, KeyError):
        pass


def get_router_from_external_ids(row, key=constants.OVN_LB_LR_REF_EXT_ID_KEY):
    router_name = get_from_external_ids(row, key)

    try:
        return router_name.replace('neutron-', "", 1)
    except AttributeError:
        pass


def get_vips_from_lb(lb):
    """Return a set of vips from a Load_Balancer row

    Note: As LB VIP contains a port (e.g., '192.168.1.1:80'), the port part
          is removed.
    """
    return {driver_utils.remove_port_from_ip(ipport)
            for ipport in getattr(row, 'vips', {})}


def _get_diff_ip_from_vips(self, new, old):
    "Return a set of IPs that are present in 'new' but not in 'old'"
    return get_vips_from_lb(new) - get_vips_from_lb(old)


def _ip_matches_in_row(row, ip, key):
    """Return True if given ip is in external_ids under given key.

    Return also True if passed ip is None and key is not present.

    Return None if external_ids is not present in row.

    Otherwise return False
    """
    try:
        return ip == row.external_ids.get(key)
    except AttributeError:
        pass


def is_lb_vip(row, ip):
    return _ip_matches_in_row(row, ip, constants.OVN_LB_VIP_IP_EXT_ID_KEY)


def is_lb_fip(row, ip):
    return _ip_matches_in_row(row, ip, constants.OVN_LB_VIP_FIP_EXT_ID_KEY)
