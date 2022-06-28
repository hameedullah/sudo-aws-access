import json
from odoo import http
from odoo.http import Response, request
import logging

from datetime import datetime


_logger = logging.getLogger(__name__)
class AWSAccessController(http.Controller):
    @http.route('/api/1/users_mapping', type='http', auth="public", method="GET")
    def accounts(self):
        result = http.request.env['sudo_aws_access.main'].sudo().search([])

        users_mapping = {}
        for r in result:
            if not r.team_member.email in users_mapping:
                users_mapping[r.team_member.email] = {"authorized_roles":[]}
            users_mapping[r.team_member.email]["authorized_roles"].append(r.role_name)
        return Response(json.dumps(users_mapping), content_type='application/json;charset=utf-8',status=200)

