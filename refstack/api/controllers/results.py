# Copyright (c) 2015 Mirantis, Inc.
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

"""Test results controller."""

from oslo_config import cfg
from oslo_log import log
import pecan
from six.moves.urllib import parse

from refstack import db
from refstack.api import constants as const
from refstack.api import utils as api_utils
from refstack.api.controllers import validation
from refstack.common import validators

LOG = log.getLogger(__name__)

CONF = cfg.CONF


class ResultsController(validation.BaseRestControllerWithValidation):

    """/v1/results handler."""

    __validator__ = validators.TestResultValidator

    def get_item(self, item_id):
        """Handler for getting item."""
        test_info = db.get_test(item_id)
        if not test_info:
            pecan.abort(404)
        test_list = db.get_test_results(item_id)
        test_name_list = [test_dict[0] for test_dict in test_list]
        return {"cpid": test_info.cpid,
                "created_at": test_info.created_at,
                "duration_seconds": test_info.duration_seconds,
                "results": test_name_list}

    def store_item(self, item_in_json):
        """Handler for storing item. Should return new item id."""
        item = item_in_json.copy()
        if pecan.request.headers.get('X-Public-Key'):
            if 'metadata' not in item:
                item['metadata'] = {}
            item['metadata']['public_key'] = \
                pecan.request.headers.get('X-Public-Key')
        test_id = db.store_results(item)
        LOG.debug(item)
        return {'test_id': test_id,
                'url': parse.urljoin(CONF.ui_url,
                                     CONF.api.test_results_url) % test_id}

    @pecan.expose('json')
    def get(self):
        """Get information of all uploaded test results.

        Get information of all uploaded test results in descending
        chronological order. Make it possible to specify some
        input parameters for filtering.
        For example:
            /v1/results?page=<page number>&cpid=1234.
        By default, page is set to page number 1,
        if the page parameter is not specified.
        """
        expected_input_params = [
            const.START_DATE,
            const.END_DATE,
            const.CPID,
        ]

        try:
            filters = api_utils.parse_input_params(expected_input_params)
            records_count = db.get_test_records_count(filters)
            page_number, total_pages_number = \
                api_utils.get_page_number(records_count)
        except api_utils.ParseInputsError as ex:
            pecan.abort(400, 'Reason: %s' % ex)
        except Exception as ex:
            LOG.debug('An error occurred: %s' % ex)
            pecan.abort(500)

        try:
            per_page = CONF.api.results_per_page
            records = db.get_test_records(page_number, per_page, filters)

            results = []
            for r in records:
                results.append({
                    'test_id': r.id,
                    'created_at': r.created_at,
                    'cpid': r.cpid,
                    'url': CONF.api.test_results_url % r.id
                })

            page = {'results': results,
                    'pagination': {
                        'current_page': page_number,
                        'total_pages': total_pages_number
                    }}
        except Exception as ex:
            LOG.debug('An error occurred during '
                      'operation with database: %s' % ex)
            pecan.abort(400)

        return page