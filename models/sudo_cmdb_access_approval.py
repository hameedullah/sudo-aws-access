from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging
from slack_sdk.webhook import WebhookClient


class SudoAccessApproval(models.Model):
    _name = 'sudo_aws_access.approval'
    _description = 'AWS Access for team'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    requester_user = fields.Many2one('res.users', string='Requester User', required=False)
    approval_user = fields.Many2many('res.users', string='Approval User', required=False,domain=lambda self: self.default_user_ids())

    current_access_user = fields.Many2one('res.users', string='Current Access User', required=False, )

    approval = fields.Selection(
        string='Approval',
        selection=[('approve', 'Approved'),
                   ('reject', 'Rejected'), ],
        required=False, )
    state = fields.Selection(
        string='Status',
        selection=[('approve', 'Approved'),
                   ('reject', 'Rejected'), ],
        required=False, )

    account_name = fields.Char(string='AWS Account')

    team_member = fields.Many2one('res.users',
                                  string='Team Member',
                                  required=False
                                  )
    role_name = fields.Char(
        string='role name',
        required=False)

    access_type = fields.Selection(
        [
            ('l1access', 'L1 Access'),
            ('l2access', 'L2 Access'),
            ('psaccess', 'PS Access'),
            ('readonlyaccess', 'Read Only Access'),
            ('supportaccess', 'Support Access'),
            ('billingaccess', 'Billing Access'),

        ])
    login_link = fields.Char("Login Link", compute='compute_login_link', widget="url")
    role_edit_link = fields.Char("Role Edit Link", default="", required=False, widget="url")
    weep_commands = fields.Html("Weep Commands", default="", required=False)
    status = fields.Selection(
        string='Status',
        selection=[('enable', 'Enable'),
                   ('disable', 'Disable'), ],
        required=False, )
    reject_reason = fields.Text(string="Rejection Reason")


    def compute_login_link(self):
        for record in self:
            if record.role_name:
                record.login_link = "https://consolemeurl.com/role/{role}".format(role=record.role_name)
            else:
                record.login_link = ''

    def approve_action(self):
        for rec in self:
            access_to_user = self.env['sudo_aws_access.main'].sudo().search(
                [('team_member', '=', rec.current_access_user.id),('role_name', '=', rec.role_name)])
            if access_to_user:
                access_to_user.write({
                    # 'status': 'disable',
                    'team_member': self.requester_user.id,
                })
            rec.approval = 'approve'
            rec.state = 'approve'
        webhook = self.env['cmdb.webhook'].sudo().search([('name', '=', 'slack-approval-notification')])
        cmdb_acces_approval = self.env.ref("sudo_aws_access.sudo_aws_access_approval_access")
        ids_cmdb_user = [usr.partner_id.name for usr in cmdb_acces_approval.users if usr.partner_id.name]
        aprroval_cmdb_user = [usr.partner_id.id for usr in cmdb_acces_approval.users]
        requester_user = self.requester_user.name
        current_access_user_id = self.current_access_user.id

        for rec in webhook:
            if rec.webhook_url:
                web_hook_url = rec.webhook_url
                url = web_hook_url
                webhook = WebhookClient(url)
                webhook_noti_body ="Your Request has been Approved:-%s" % (
                    str(requester_user))
                response = webhook.send(text=webhook_noti_body)
            else:
                pass
        group_user_send = aprroval_cmdb_user
        group_user_send.append(current_access_user_id)
        self.message_post(
            subject="",
            # body='Request Approved',
            body="Your Request Has been Approved:%s" % (
                str(requester_user)),
            message_type='notification',
            partner_ids=group_user_send
        )
        mailqueue = self.env["mail.mail"]
        mailqueue.sudo().process_email_queue()

    def reject_action(self):
        if self.state == 'reject':
            raise UserError(_("Already Rejected!!"))
        else:
            return {
                'name': "Rejection Wizard",
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sudo_aws_access.reject.reason',
                'view_id': self.env.ref('sudo_aws_access.sudo_aws_access_reject_reason').id,
                'target': 'new'
            }

    def default_user_ids(self):
        group_user = []
        all_users = self.env['res.users'].search([])
        for rec in all_users:
            if rec.has_group('sudo_aws_access.sudo_aws_access_approval_access'):
                group_user.append(rec.id)
            else:
                continue

        return [('id', 'in', group_user)]

