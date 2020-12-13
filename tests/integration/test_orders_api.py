# Copyright 2020 Planet Labs, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
import copy
import json
import logging
import os
from pathlib import Path

import pytest

from planet.api import OrdersClient


DATA_DIR = Path(os.path.dirname(__file__)).parents[0] / 'data'

LOGGER = logging.getLogger(__name__)

# if use mock:// as the prefix, the params get lost
# https://github.com/jamielennox/requests-mock/issues/142
TEST_URL = 'http://MockNotRealURL/'


@pytest.fixture()
def orders_client():
    return OrdersClient(api_key='doesntmatter', base_url=TEST_URL)


@pytest.fixture
def order_description():
    order_name = 'order_description_b0cb3448-0a74-11eb-92a1-a3d779bb08e0.json'
    order_filename = DATA_DIR / order_name
    return json.load(open(order_filename, 'r'))


@pytest.fixture
def order_details():
    order_name = 'order_details_psorthotile_analytic.json'
    order_filename = DATA_DIR / order_name
    return json.load(open(order_filename, 'r'))


@pytest.fixture
def oid():
    return 'b0cb3448-0a74-11eb-92a1-a3d779bb08e0'


@pytest.fixture
def open_test_img():
    img_path = DATA_DIR / 'test_sm.tif'
    with open(img_path, 'rb') as img:
        yield img


def test_get_order(requests_mock, orders_client, oid, order_description):
    get_url = TEST_URL + 'orders/v2/' + oid
    requests_mock.get(get_url, status_code=200, json=order_description)
    state = orders_client.get_order(oid).state
    assert state == 'queued'


def test_list_orders(requests_mock, orders_client, order_description):
    list_url = TEST_URL + 'orders/v2/'
    next_page_url = list_url + '?page_marker=IAmATest'

    order1 = copy.deepcopy(order_description)
    order1['id'] = 'oid1'
    order2 = copy.deepcopy(order_description)
    order2['id'] = 'oid2'
    order3 = copy.deepcopy(order_description)
    order3['id'] = 'oid3'

    page1_response = {
        "_links": {
            "_self": "string",
            "next": next_page_url},
        "orders": [order1, order2]
    }
    requests_mock.get(list_url, status_code=200, json=page1_response)

    page2_response = {
        "_links": {
            "_self": next_page_url},
        "orders": [order3]
    }
    requests_mock.get(next_page_url, status_code=200, json=page2_response)

    orders = orders_client.list_orders()
    oids = list(o.id for o in orders)
    assert oids == ['oid1', 'oid2', 'oid3']


def test_list_orders_state(requests_mock, orders_client, order_description):
    list_url = TEST_URL + 'orders/v2/?state=failed'

    order1 = copy.deepcopy(order_description)
    order1['id'] = 'oid1'
    order2 = copy.deepcopy(order_description)
    order2['id'] = 'oid2'

    page1_response = {
        "_links": {
            "_self": "string"
        },
        "orders": [order1, order2]
    }
    requests_mock.get(list_url, status_code=200, json=page1_response)

    orders = orders_client.list_orders(state='failed')
    oids = list(o.id for o in orders)
    assert oids == ['oid1', 'oid2']


def test_list_orders_limit(requests_mock, orders_client, order_description):
    list_url = TEST_URL + 'orders/v2/'
    next_page_url = list_url + '?page_marker=IAmATest'

    order1 = copy.deepcopy(order_description)
    order1['id'] = 'oid1'
    order2 = copy.deepcopy(order_description)
    order2['id'] = 'oid2'
    order3 = copy.deepcopy(order_description)
    order3['id'] = 'oid3'

    # check that the client doesn't try to get the next page when the
    # limit is already reached by providing link to next page but not
    # registering a response. if the client tries to get the next
    # page, an error will occur
    page1_response = {
        "_links": {
            "_self": "string",
            "next": next_page_url},
        "orders": [order1, order2]
    }
    requests_mock.get(list_url, status_code=200, json=page1_response)

    orders = orders_client.list_orders(limit=1)
    oids = list(o.id for o in orders)
    assert oids == ['oid1']


def test_create_order(requests_mock, orders_client, oid, order_description,
                      order_details):
    create_url = TEST_URL + 'orders/v2/'
    requests_mock.post(create_url, status_code=200, json=order_description)

    created_oid = orders_client.create_order(order_details)
    assert created_oid == oid


def test_cancel_order(requests_mock, orders_client, oid):
    # TODO: the api says cancel order returns the order details but as
    # far as I can test thus far, it returns nothing. follow up on this
    cancel_url = TEST_URL + 'orders/v2/' + oid
    requests_mock.put(cancel_url, status_code=200, text='')

    orders_client.cancel_order(oid)


def test_cancel_orders(requests_mock, orders_client):
    bulk_cancel_url = TEST_URL + 'bulk/orders/v2/cancel'

    test_ids = ["oid1", "oid2", "oid3"]
    example_result = {
        "result": {
            "succeeded": {"count": 2},
            "failed": {
                "count": 1,
                "failures": [
                    {
                        "order_id": "oid3",
                        "message": "bummer"
                    }
                ]
            }
        }
    }
    requests_mock.post(bulk_cancel_url, status_code=200, json=example_result)

    res = orders_client.cancel_orders(test_ids)
    assert res == example_result

    expected_body = {
            "order_ids": test_ids
    }
    history = requests_mock.request_history
    assert history[0].json() == expected_body


def test_cancel_orders_all(requests_mock, orders_client):
    bulk_cancel_url = TEST_URL + 'bulk/orders/v2/cancel'

    example_result = {
        "result": {
            "succeeded": {"count": 2},
            "failed": {
                "count": 0,
                "failures": []
            }
        }
    }
    requests_mock.post(bulk_cancel_url, status_code=200, json=example_result)

    res = orders_client.cancel_orders([])
    assert res == example_result

    history = requests_mock.request_history
    assert history[0].json() == {}


def test_aggegated_order_stats(requests_mock, orders_client):
    stats_url = TEST_URL + 'stats/orders/v2/'
    LOGGER.debug('url: {}'.format(stats_url))
    example_stats = {
        "organization": {
            "queued_orders": 0,
            "running_orders": 6
        },
        "user": {
            "queued_orders": 0,
            "running_orders": 0
        }
    }
    requests_mock.get(stats_url, status_code=200, json=example_stats)

    res = orders_client.aggregated_order_stats()
    assert res == example_stats


def test_download_asset(requests_mock, tmpdir, orders_client, open_test_img):
    dl_url = TEST_URL + 'download/?token=IAmAToken'

    with open_test_img as img:
        requests_mock.get(
            dl_url,
            status_code=200,
            body=img,
            headers={
                'Content-Type': 'image/tiff',
                'Content-Length': '527'
            })

        filename = orders_client.download_asset(
                dl_url, directory=str(tmpdir))
        assert os.path.isfile(filename)


@pytest.mark.skip(reason='not implemented')
def test_poll(ordersapi):
    pass
    # cl = OrdersClient(api_key=TEST_API_KEY, base_url=ordersapi)

    # cl.poll(TEST_OID)

    # TODO: assert that this exits out if state isn't queued or running or
    # some finished state, check that it waits until the state is no longer
    # running and that it gracefully handles other states
    # maybe break all those into separate tests
    # need ordersapi to be able to return different responses so state changes
