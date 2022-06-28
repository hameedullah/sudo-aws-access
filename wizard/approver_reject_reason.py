from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import time
import json
import logging
from slack_sdk.webhook import WebhookClient


class ApproverRejectReason(models.TransientModel):
    _name = "sudo_aws_access.reject.reason"
    _description = 'Approver Reject Reason'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    reject_reason = fields.Text(string="Rejection Reason")

    def rejection_reason(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', [])
        rejection_reason = self.env['sudo_aws_access.approval'].sudo().browse(active_ids)
        rejection_email_send = []
        webhook = self.env['cmdb.webhook'].sudo().search([('name', '=', 'slack-approval-notification')])
        for i in rejection_reason:
            requester_user_name = i.requester_user.name
            rejection_email_send.append(i.requester_user.id)

            val = {
                'reject_reason': self.reject_reason,
                'approval': 'reject',
                'state': 'reject',
            }
            rejection_reason.write(val)

        for rec in webhook:
            if rec.webhook_url:
                web_hook_url = rec.webhook_url
                url = web_hook_url
                webhook = WebhookClient(url)
                webhook_noti_body = "Requester User:%s\nRejection Reason: %s" % (
                        str(requester_user_name), str(self.reject_reason))
                response = webhook.send(text=webhook_noti_body)
            else:
                pass

        rejection_reason.message_post(
            subject="",
            body="Requester User:%s<br/>Rejection Reason: %s" % (
                str(requester_user_name),str(self.reject_reason)),
            message_type='notification',
            partner_ids= rejection_email_send
        )
        mailqueue = self.env["mail.mail"].sudo()
        mailqueue.sudo().process_email_queue()
