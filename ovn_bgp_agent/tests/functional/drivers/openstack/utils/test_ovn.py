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
from ovn_bgp_agent.drivers.openstack.utils import ovn as ovn_utils
from ovn_bgp_agent.tests.functional import base


class OvsdbNbOvnIdl(base.BaseFunctionalNorthboundTestCase):
    def _lsp_add(self, ls_name, lsp_name, type_, tag):
        self.api.lsp_add(ls_name, lsp_name, type=type_).execute(
            check_error=True)
        # lsp_add requires parent to be specified with the tag, work it
        # around with the db_set
        self.api.db_set(
            'Logical_Switch_Port', lsp_name, ('tag', tag)).execute(
                check_error=True)

    def test_get_network_vlan_tags(self):
        # 0 is not a valid tag, let's start with 1
        expected_tags = list(range(1, 4))
        len_tags = len(expected_tags)

        for i, tag in enumerate(expected_tags):
            self.api.ls_add('ls%d' % i).execute(check_error=True)
            ls_name = 'ls%d' % (i % 2)
            lsp_name = 'localnetport%d' % i
            self._lsp_add(
                ls_name, lsp_name,
                constants.OVN_LOCALNET_VIF_PORT_TYPE, tag=tag)
        for i, tag in enumerate(expected_tags):
            ls_name = 'ls%d' % i
            lsp_name = 'port%d' % i
            self._lsp_add(
                ls_name, lsp_name,
                type_=None, tag=i + len_tags)

        tags = sorted(self.api.get_network_vlan_tags())
        self.assertEqual(expected_tags, tags)


class GetLSPsForGwChassisCommandTestCase(
        base.BaseFunctionalNorthboundTestCase):
    # format is 10.0.<router>.<switch>*10 + <port>
    FIP_TEMP = '10.0.%d.%d'
    GW_MAC_TEMP = '00:00:00:00:00:%d0'

    def setUp(self):
        super().setUp()
        with self.api.transaction(check_error=True) as txn:
            for switch in range(6):
                txn.add(self.api.ls_add('ls%d' % switch))
                for switch_port in range(4):
                    txn.add(self.api.lsp_add(
                        'ls%d' % switch, 'lsp%d-%d' % (switch, switch_port)))
            for router in range(3):
                router_name = 'lr%d' % router
                txn.add(self.api.lr_add(router_name, nat=[]))
                # gateway port
                txn.add(self.api.lrp_add(
                    'lr%d' % router,
                    'lrp%d-0' % router,
                    self.GW_MAC_TEMP % router,
                    ['10.0.%d.0/24' % router],
                    status={
                        constants.OVN_STATUS_CHASSIS: 'chassis%d' % (
                            router % 2)}))
                # connect two switches to the router
                for lrp_index, lrp_peer in enumerate([1, 2]):
                    ls_index = router + lrp_peer * 2
                    network = '192.168.%d.0/24' % ls_index
                    txn.add(self.api.lrp_add(
                        router_name,
                        'lrp%d-%d' % (router, lrp_peer),
                        '00:00:00:00:00:%d%d' % (router, lrp_index),
                        [network],
                        peer='lsp%d-0' % ls_index))
                    txn.add(self.api.lr_nat_add(
                        router_name,
                        constants.OVN_SNAT,
                        '10.0.%d.1' % router,
                        network))

            # Add DNAT rules to ports on one switch 2 NATs, then 1 NAT,
            # and so on
            for router, switch in enumerate(range(0, 6, 2)):
                for lsp in range(1, 3):
                    nat = txn.add(self.api.lr_nat_add(
                        'lr%d' % router,
                        constants.OVN_DNAT_AND_SNAT,
                        self.FIP_TEMP % (router, switch * 10 + lsp),
                        '192.168.%d.%d' % (switch, lsp),
                        logical_port='lsp%d-%d' % (switch, lsp),
                        external_mac='00:00:00:00:0%d:0%d' % (switch, lsp)))
                switch += 1
                nat = txn.add(self.api.lr_nat_add(
                    'lr%d' % router,
                    constants.OVN_DNAT_AND_SNAT,
                    self.FIP_TEMP % (router, switch *10 + 1),
                    '192.168.%d.1' % switch,
                    logical_port='lsp%d-1' % switch,
                    external_mac='00:00:00:00:0%d:01' % switch))

        # Set the gateway ports for all NATs
        for router in range(3):
            for nat in self.api.lr_nat_list(
                    'lr%d' % router).execute(check_error=True):
                lrp = self.api.lrp_get(
                    'lrp%d-0' % router).execute(check_error=True)
                self.api.db_set(
                    'NAT',
                    nat.uuid,
                    ('gateway_port', lrp),
                    ('external_ids', {
                        constants.OVN_FIP_NET_EXT_ID_KEY: 'external'})
                ).execute(check_error=True)

    def _make_fip_result(self, router_index, switch_index, lsp_index):
        lsp = self.api.lsp_get(
            'lsp%d-%d' % (switch_index, lsp_index)).execute(check_error=True)
        return (self.FIP_TEMP % (router_index, switch_index * 10 + lsp_index),
                self.GW_MAC_TEMP % router_index,
                'neutron-external',
                lsp)

    def _get_expected_fips(self):
        expected_found_fips = []

        for router in [0, 2]:
            switch = router * 2
            # 2 FIPs on the first switch
            for lsp in [1, 2]:
                expected_found_fips.append(
                    self._make_fip_result(router, switch, lsp))

            # 1 FIP on the second switch
            switch = router * 2 + 1
            expected_found_fips.append(
                self._make_fip_result(router, switch, lsp_index=1))

        return expected_found_fips

    def test_get_lsps(self):
        # We expect only LSPs from switches attached to routers 0 and 2
        # each router has w switches. The first switch has 2 FIPs and the
        # second has one FIP. That is 6 FIPs in total.
        expected_found_fips = self._get_expected_fips()
        result = ovn_utils.GetLSPsForGwChassisCommand(
            self.api, 'chassis0').execute()

        self.assertCountEqual(expected_found_fips, result)
