# Copyright 2024 Red Hat, Inc.
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

from ovn_bgp_agent import constants
from ovn_bgp_agent.drivers.openstack.watchers import utils
from ovn_bgp_agent.tests import base as test_base
from ovn_bgp_agent.tests import utils as test_utils


class TestHasIpAddressDefined(test_base.TestCase):
    def test_no_ip_address(self):
        self.assertFalse(
            utils.has_ip_address_defined('aa:bb:cc:dd:ee:ff'))

    def test_one_ip_address(self):
        self.assertTrue(
            utils.has_ip_address_defined('aa:bb:cc:dd:ee:ff 10.10.1.16'))

    def test_two_ip_addresses(self):
        self.assertTrue(
            utils.has_ip_address_defined(
                'aa:bb:cc:dd:ee:ff 10.10.1.16 10.10.1.17'))

    def tets_three_ip_addresses(self):
        self.assertTrue(
            utils.has_ip_address_defined(
                'aa:bb:cc:dd:ee:ff 10.10.1.16 10.10.1.17 10.10.1.18'))


class TestGetFromExternalIds(test_base.TestCase):
    def test_all_present(self):
        key = 'foo'
        value = 'bar'
        row = test_utils.create_row(external_ids={key: value})

        observed_value = utils.get_from_external_ids(row, key)
        self.assertEqual(value, observed_value)

    def test_external_ids_missing(self):
        row = test_utils.create_row()

        self.assertIsNone(utils.get_from_external_ids(row, 'key'))

    def test_key_missing(self):
        row = test_utils.create_row(external_ids={})

        self.assertIsNone(utils.get_from_external_ids(row, 'key'))


class TestGetRouterFromExternalIds(test_base.TestCase):
    def test_router_present(self):
        expected_router = 'foo'
        r_ext_id = 'neutron-{:s}'.format(expected_router)
        row = test_utils.create_row(
            external_ids={
                constants.OVN_LB_LR_REF_EXT_ID_KEY: r_ext_id})
        router = utils.get_router_from_external_ids(row)

        self.assertEqual(expected_router, router)

    def test_router_present_custom_field(self):
        expected_router = 'foo'
        custom_field = 'bar'
        r_ext_id = 'neutron-{:s}'.format(expected_router)
        row = test_utils.create_row(
            external_ids={custom_field: r_ext_id})
        router = utils.get_router_from_external_ids(row, key=custom_field)

        self.assertEqual(expected_router, router)

    def test_router_missing(self):
        row = test_utils.create_row(external_ids={})
        router = utils.get_router_from_external_ids(row)

        self.assertIsNone(router)

    def test_router_missing_custom_field(self):
        row = test_utils.create_row(external_ids={})
        router = utils.get_router_from_external_ids(row, key='foo')

        self.assertIsNone(router)

    def test_router_bad_name(self):
        expected_router = 'foo'
        row = test_utils.create_row(
            external_ids={
                constants.OVN_LB_LR_REF_EXT_ID_KEY: expected_router})
        router = utils.get_router_from_external_ids(row)

        self.assertEqual(expected_router, router)


class Test_IpMatchesInRow(test_base.TestCase):
    def test_ip_is_in_row(self):
        ip = 'ip'
        key = 'key'
        row = test_utils.create_row(external_ids={
            key: ip})

        self.assertTrue(utils._ip_matches_in_row(row, ip, key))

    def test_external_ids_missing_returns_none(self):
        ip = 'ip'
        key = 'key'
        row = test_utils.create_row()

        self.assertIsNone(utils._ip_matches_in_row(row, ip, key))

    def test_key_missing(self):
        ip = 'ip'
        key = 'key'
        row = test_utils.create_row(external_ids={})

        self.assertFalse(utils._ip_matches_in_row(row, ip, key))

    def test_key_missing_but_ip_is_none(self):
        ip = None
        key = 'key'
        row = test_utils.create_row(external_ids={})

        self.assertTrue(utils._ip_matches_in_row(row, ip, key))


class TestIsLbVip(test_base.TestCase):
    def test_is_lb_vip(self):
        ip = 'ip'
        row = test_utils.create_row(
            external_ids={constants.OVN_LB_VIP_IP_EXT_ID_KEY: ip})

        self.assertTrue(utils.is_lb_vip(row, ip))


class TestIsLbFip(test_base.TestCase):
    def test_is_lb_fip(self):
        ip = 'ip'
        row = test_utils.create_row(
            external_ids={constants.OVN_LB_VIP_FIP_EXT_ID_KEY: ip})

        self.assertTrue(utils.is_lb_fip(row, ip))
