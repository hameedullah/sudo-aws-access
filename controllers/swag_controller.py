import json
from odoo import http
from odoo.http import Response, request
import logging

from datetime import datetime


_logger = logging.getLogger(__name__)
class SwagController(http.Controller):

    @http.route('/api/1/scan_accounts', type='http', auth="public", method="GET")
    def scan_accounts(self):
        # get the information using the SUPER USER
        #http.request.env['sudo_ace_crm.sudo_ace_crm'].search([]),
        result = http.request.env['module.'].sudo().search([])

        result = [self.swagify(r) for r in result]
        return Response(json.dumps(result), content_type='application/json;charset=utf-8',status=200)

    @http.route('/api/1/accounts', type='http', auth="public", method="GET")
    def accounts(self):
        # get the information using the SUPER USER
        #http.request.env['sudo_ace_crm.sudo_ace_crm'].search([]),
        result = http.request.env['module.'].sudo().search([])
        #.read(['serial_asset_tag','account_status','sensitive','environment','aliases'])
        result = [self.swagify(r) for r in result]
        return Response(json.dumps(result), content_type='application/json;charset=utf-8',status=200)

    def swagify(self, account):
        swag_account = {}
        if account['serial_asset_tag']:
            _logger.debug(account.customer.id)
            swag_account['customer_id'] = account.customer.id
            swag_account['id'] = account['serial_asset_tag']
            swag_account['account_status'] = account['account_status']
            if account['unique_asset_identifier']:
                swag_account['name'] = account['unique_asset_identifier']
            else:
                swag_account['name'] = 'sudo' + str(swag_account['id'])
            if account['environment']:
                swag_account['environment'] = account['environment']
            else:
                swag_account['environment'] = 'prod'
            swag_account['sensitive'] = False
            swag_account['email'] = "support@domain.com"
            if account['unique_asset_identifier']:
                swag_account['aliases'] = [account['aliases']]
            else:
                swag_account['aliases'] = []
            if account['regions_to_scan']:
                swag_account['regions_to_scan'] = account['regions_to_scan']
            else:
                swag_account['regions_to_scan'] = 'us-east-1,us-west-2,us-east-2,us-west-1'
        return swag_account