# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging
from botocore.exceptions import ClientError
from slack_sdk.webhook import WebhookClient
from datetime import timedelta, datetime
from datetime import date

from odoo.http import request

_logger = logging.getLogger(__name__)

import boto3
from botocore.exceptions import ClientError

_logger = logging.getLogger(__name__)


def add_role_to_the_queue(role_name, account_id):
    """Add role to the SQS queue

    :param role_name: string
    """

    try:
        sqs_client = boto3.resource('sqs', "us-east-1")
        queue = sqs_client.get_queue_by_name(QueueName='<QUEUENAME>',QueueOwnerAWSAccountId='<AWSACCOUTN>')
        response = queue.send_message(MessageBody=json.dumps({
            "detail": {
                "requestParameters": {
                    "roleName": role_name
                },
                "recipientAccountId": account_id
            }
        })
        )
    except ClientError as e:
        _logger.error(e)
        return None

    return response


weep_instructions = """
<br /><br />
<h3># To load crednetials in environment</h3>
<b>$</b> eval $(weep export {role})
<br /><br />
<h3>To Open console</h3>
<b>$</b> weep console {role}
<br />
<br />
<strong>For Weep Setup Instructions:</strong> <a href="https://howto/howtouseweep">https://howto/howtouseweep</a>
<br />
"""


class SUDOAWSAccess(models.Model):
    _name = 'sudo_aws_access.main'
    _description = 'AWS Access for team'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    ci = fields.Many2many('sudo_cmdb.main', string='Cloud Account')

    account_name = fields.Char(string='AWS Account')

    team_member = fields.Many2one('res.users',
                                  string='Team Member',
                                  required=False, tracking=True
                                  )
    role_name = fields.Char(
        string='role name',
        required=False, tracking=True, )

    status = fields.Selection(
        string='Status',
        selection=[('enable', 'Enable'),
                   ('disable', 'Disable'), ],
        required=False, )

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

    def compute_login_link(self):
        for record in self:
            if record.role_name:
                record.login_link = "https://consolemeurl.com/role/{role}".format(role=record.role_name)
            else:
                record.login_link = ''

    # def compute_account_name(self):
    #     for record in self:
    #         record.account_name = record.ci.unique_asset_identifier

    # @api.model
    # def create(self, vals):
    #     for record in self:
    #         vals['account_name'] = record.ci.unique_asset_identifier
    #     return super(SUDOAWSAccess, self).create(vals)

    def unlink(self):
        try:
            role_tokens = self.role_name.split(':')
            role_name = role_tokens[-1].split('/')[-1]
            account_id = role_tokens[4]
            add_role_to_the_queue(role_name, account_id)
        except:
            _logger.error("Failed to send to queue for deletion")
        res = super(SUDOAWSAccess, self).unlink()
        return res


class CMDBInherit(models.Model):
    _inherit = 'sudo_cmdb.main'

    access_list_count = fields.Integer(compute='compute_access_list_count')
    account_type = fields.Char("Login Link", compute='compute_account_type')

    def compute_account_type(self):
        for record in self:
            if not record.unique_asset_identifier:
                record.account_type = False
            elif record.unique_asset_identifier.startswith("ps"):
                record.account_type = "psaccount"
            elif record.unique_asset_identifier.startswith("sudo"):
                record.account_type = "internal"
            else:
                record.account_type = "customer"
            _logger.debug("ACCOUNT TYPE:")
            _logger.debug(record.account_type)

    def sudo_aws_access_list(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Access List',
            'view_mode': 'tree,form',
            'res_model': 'sudo_aws_access.main',
            'domain': [('ci.id', '=', self.id)],
            'context': "{'create': False}"
        }

    def compute_access_list_count(self):
        for record in self:
            if record.customer:
                record.access_list_count = self.env['sudo_aws_access.main'].sudo().search_count(
                    [('ci.id', '=', self.id)])
            else:
                record.access_list_count = 0

    def get_l1_account_access(self):

        role_edit_link = 'https://consolemeurl.com/policies/edit/' + str(
            self.serial_asset_tag) + '/iamrole/sudo-ms-l1-team-role'
        role_name = 'arn:aws:iam::' + str(self.serial_asset_tag) + ':role/sudo-ms-l1-team-role'
        current_access = self.env['sudo_aws_access.main'].sudo().search(
            [('role_name', '=', role_name)])

        access_type = "l1access"

        weep_commands = weep_instructions.format(role=role_name)
        is_admin = self.env.user.has_group('sudo_aws_access.sudo_aws_access_admin_access')
        if is_admin:
            admin_access = self.env['sudo_aws_access.main'].sudo().search(
                [('role_name', '=', role_name), ('team_member', '=', self.env.uid)])
        if not current_access or (is_admin and not admin_access):
            self.env['sudo_aws_access.main'].sudo().create({
                'ci': self,
                'team_member': self.env.user.id,
                'role_name': role_name,
                'access_type': access_type,
                'role_edit_link': role_edit_link,
                'weep_commands': weep_commands,
                'account_name': self.unique_asset_identifier
            })
            add_role_to_the_queue("sudo-ms-l1-team-role", str(self.serial_asset_tag))
        else:
            raise UserError(_("Access already exist, please ask the user to remove their access first."))

    def get_l2_account_access(self):
        if self.unique_asset_identifier.startswith("ps"):
            raise UserError(_("You can not get request l2 access on PS accounts"))
        role_edit_link = 'https://consolemeurl.com/policies/edit/' + str(
            self.serial_asset_tag) + '/iamrole/sudo-ms-l2-team-role'
        role_name = 'arn:aws:iam::' + str(self.serial_asset_tag) + ':role/sudo-ms-l2-team-role'

        access_type = "l2access"

        weep_commands = weep_instructions.format(role=role_name)
        is_admin = self.env.user.has_group('sudo_aws_access.sudo_aws_access_admin_access')
        webhook = self.env['cmdb.webhook'].sudo().search([('name', '=', 'slack-approval-notification')])

        if self.serial_asset_tag == "162042740788":  # if dev account everybody can get access
            is_admin = True
        # if is_admin:
        # 	admin_access = self.env['sudo_aws_access.main'].sudo().search(
        # 		[('role_name', '=', role_name), ('team_member', '=', self.env.uid)])

        normal_user = self.env.user.has_group('sudo_aws_access.sudo_aws_access_l2_access')
        l2_users = self.env.ref('sudo_aws_access.sudo_aws_access_l2_access').users.ids
        l2_admins = self.env.ref('sudo_aws_access.sudo_aws_access_admin_access').users.ids
        normal_users = set(l2_users) - set(l2_admins)
        sudo_access_role_name = self.env['sudo_aws_access.main'].sudo().search([]).mapped('role_name')
        current_user_id = self.env.uid
        admin_ids = []
        if role_name in sudo_access_role_name:
            # for normal_user search
            if current_user_id in list(normal_users):
                get_related_rec = self.env['sudo_aws_access.main'].sudo().search([('role_name', '=', role_name), ('team_member.id', 'in', list(normal_users))])
                for i in get_related_rec:
                    team_member_id = i.team_member.id
                    admin_ids.append(team_member_id)

            # for admin_user search
            if current_user_id in list(l2_admins):
                get_related_rec = self.env['sudo_aws_access.main'].search([('role_name', '=', role_name), ('team_member.id', 'in', list(l2_admins))])
                for admin_record in get_related_rec:
                    team_member_id = admin_record.team_member.id
                    admin_ids.append(team_member_id)

            if current_user_id in admin_ids:
                raise UserError(_("You have already Access!!!"))
            if current_user_id in list(normal_users) and current_user_id != get_related_rec.team_member.id and get_related_rec.team_member.id in list(normal_users) or get_related_rec.team_member.id in list(l2_admins):
                """this (code) request is used when user have already access and new user request to access  of this record
                 New request/Approval are created and send message/notification to Admin """
                group_user = []
                all_users = self.env['res.users'].sudo().search([])
                for rec in all_users:
                    if rec.has_group('sudo_aws_access.sudo_aws_access_approval_access'):
                        group_user.append(rec.id)
                    else:
                        continue

                cmdb_acces_approval = self.env.ref("sudo_aws_access.sudo_aws_access_approval_access")
                ids_cmdb_user = [usr.partner_id.name for usr in cmdb_acces_approval.users if usr.partner_id.name]
                # aprroval_cmdb_user = [usr.partner_id.email for usr in cmdb_acces_approval.users if usr.partner_id.email]
                aprroval_cmdb_user = [usr.partner_id.id for usr in cmdb_acces_approval.users]
                requester_user = self.env.user.name
                current_access_user = get_related_rec.team_member.name
                current_access_user_id = get_related_rec.team_member.id
                base_url = self.env['ir.config_parameter'].get_param('web.base.url')
                base_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)

                for rec in webhook:
                    if rec.webhook_url:
                        web_hook_url = rec.webhook_url
                        url = web_hook_url
                        webhook = WebhookClient(url)
                        webhook_noti_body = "Approver:%s\nCurrent Access User	: %s\nRequester  User:%s\nLink: %s" % (
                            str(ids_cmdb_user), str(current_access_user), str(requester_user), str(base_url))

                        response = webhook.send(text=webhook_noti_body)
                    else:
                        pass
                group_user_send = aprroval_cmdb_user
                group_user_send.append(current_access_user_id)

                self.message_post(
                    subject="",
                    body="Requested to Approval:%s<br/>current_access_user: %s<br/>Requester User: %s<br/>Link: %s" % (
                        str(ids_cmdb_user), str(current_access_user), str(requester_user), str(base_url)),
                    message_type='notification',
                    partner_ids=group_user_send
                )
                mailqueue = self.env["mail.mail"]
                mailqueue.sudo().process_email_queue()

                # create Record in sudo_aws_access Approval
                self.env['sudo_aws_access.approval'].sudo().create({
                    'requester_user': current_user_id,
                    'current_access_user': get_related_rec.team_member.id,
                    'approval_user': [(4, u_id) for u_id in group_user],
                    # 'team_member': team_member_user.team_member.id,
                    'role_name': role_name,
                    'access_type': access_type,
                    'status': 'enable',
                    'role_edit_link': role_edit_link,
                    'weep_commands': weep_commands,
                    'account_name': self.unique_asset_identifier
                })
                self.env.cr.commit()

                raise UserError(_("Request Send To Admin"))
            elif current_user_id in list(l2_admins):
                self.create_sudo_aws_access_record(role_name, access_type, role_edit_link, weep_commands)
            # raise UserError(_("New user fjslkfjsldfsdflkj"))

            else:
                """this (code)/request is run when Admin have already access and new user request to access  of this record
                             New request/Approval are created and send message/notification to Admin """

                group_user = []
                all_users = self.env['res.users'].sudo().search([])
                for rec in all_users:
                    if rec.has_group('sudo_aws_access.sudo_aws_access_approval_access'):
                        group_user.append(rec.id)
                    else:
                        continue

                cmdb_acces_approval = self.env.ref("sudo_aws_access.sudo_aws_access_approval_access")
                ids_cmdb_user = [usr.partner_id.name for usr in cmdb_acces_approval.users if usr.partner_id.name]
                aprroval_cmdb_user = [usr.partner_id.id for usr in cmdb_acces_approval.users]
                requester_user = self.env.user.name
                current_access_user = ids_cmdb_user
                # current_access_user_id = aprroval_cmdb_user
                base_url = self.env['ir.config_parameter'].get_param('web.base.url')
                base_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
                current_record_admin = self.env['sudo_aws_access.main'].sudo().search([('role_name', '=', role_name), ('team_member.id', 'in', list(l2_admins))], limit=1)

                for rec in webhook:
                    if rec.webhook_url:
                        web_hook_url = rec.webhook_url
                        url = web_hook_url
                        webhook = WebhookClient(url)
                        webhook_noti_body = "Approver:%s\nCurrent Access User	: %s\nRequester  User:%s\nLink: %s" % (
                            str(ids_cmdb_user), str(current_access_user), str(requester_user), str(base_url))

                        response = webhook.send(text=webhook_noti_body)
                    else:
                        pass
                group_user_send = aprroval_cmdb_user
                self.message_post(
                    subject="",
                    body="Requested to Approval:%s<br/>current_access_user: %s<br/>Requester User: %s<br/>Link: %s" % (
                        str(ids_cmdb_user), str(current_access_user), str(requester_user), str(base_url)),
                    message_type='notification',
                    partner_ids=group_user_send
                )
                mailqueue = self.env["mail.mail"]
                mailqueue.sudo().process_email_queue()

                # create Record in sudo_aws_access Approval
                self.env['sudo_aws_access.approval'].sudo().create({
                    'requester_user': current_user_id,
                    'current_access_user': current_record_admin.team_member.id,
                    'approval_user': [(4, u_id) for u_id in group_user],
                    # 'team_member': team_member_user.team_member.id,
                    'role_name': role_name,
                    'access_type': access_type,
                    'status': 'enable',
                    'role_edit_link': role_edit_link,
                    'weep_commands': weep_commands,
                    'account_name': self.unique_asset_identifier
                })
                self.env.cr.commit()

                raise UserError(_("Request Send To Admin"))
        # else:
        # 	self.create_sudo_aws_access_record(role_name, access_type, role_edit_link, weep_commands)
        else:
            if current_user_id in list(normal_users):
                """When normal user get first time access of record this message/notification are created """
                for rec in webhook:
                    if rec.webhook_url:
                        web_hook_url = rec.webhook_url
                        url = web_hook_url
                        webhook = WebhookClient(url)
                        webhook_noti_body = "New AWS Access are created by :%s " % (
                            str(self.env.user.name))
                        response = webhook.send(text=webhook_noti_body)
                    else:
                        pass
                send_email_to_admin = self.env.ref("sudo_aws_access.sudo_aws_access_admin_access")
                # ids_cmdb_user = [usr.partner_id.name for usr in send_email_to_admin.users if usr.partner_id.name]
                aprroval_cmdb_user = [usr.partner_id.id for usr in send_email_to_admin.users]
                group_user_send = aprroval_cmdb_user

                self.message_post(
                    subject="",
                    body="New AWS access request is created by :%s " % (
                        str(self.env.user.name)),
                    message_type='notification',
                    partner_ids=group_user_send
                )
                mailqueue = self.env["mail.mail"]
                mailqueue.sudo().process_email_queue()
                self.create_sudo_aws_access_record(role_name, access_type, role_edit_link, weep_commands)
            else:
                self.create_sudo_aws_access_record(role_name, access_type, role_edit_link, weep_commands)

    def create_sudo_aws_access_record(self, r_name=None, acc_type=None, red=None, wp=None):
        self.env['sudo_aws_access.main'].sudo().create({
            'ci': self,
            'team_member': self.env.user.id,
            'role_name': r_name,
            'access_type': acc_type,
            'status': 'enable',
            'role_edit_link': red,
            'weep_commands': wp,
            'account_name': self.unique_asset_identifier
        })

        add_role_to_the_queue("sudo-ms-l2-team-role", str(self.serial_asset_tag))

    def get_ps_account_access(self):
        if not self.unique_asset_identifier.startswith("ps"):
            raise UserError(_("Professional services AWS account name should start with ps"))
        role_edit_link = 'https://consolemeurl.com/policies/edit/' + str(
            self.serial_asset_tag) + '/iamrole/sudo-implementation-role'
        role_name = 'arn:aws:iam::' + str(self.serial_asset_tag) + ':role/sudo-implementation-role'
        current_access = self.env['sudo_aws_access.main'].sudo().search(
            [('role_name', '=', role_name)])

        access_type = "psaccess"

        weep_commands = weep_instructions.format(role=role_name)
        is_admin = self.env.user.has_group('sudo_aws_access.sudo_aws_access_admin_access')
        if is_admin:
            admin_access = self.env['sudo_aws_access.main'].sudo().search(
                [('role_name', '=', role_name), ('team_member', '=', self.env.uid)])
        if not current_access or (is_admin and not admin_access):
            self.env['sudo_aws_access.main'].sudo().create({
                'ci': self,
                'team_member': self.env.user.id,
                'role_name': role_name,
                'access_type': access_type,
                'role_edit_link': role_edit_link,
                'weep_commands': weep_commands,
                'account_name': self.unique_asset_identifier  # temporary fix, should read it from ci
            })
            add_role_to_the_queue("sudo-implementation-role", str(self.serial_asset_tag))
        else:
            raise UserError(_("Access already exist, please ask the user to remove their access first."))

    def get_support_access(self):
        role_name = 'arn:aws:iam::' + str(self.serial_asset_tag) + ':role/sudo-ms-support-role'
        current_access = self.env['sudo_aws_access.main'].sudo().search(
            [('role_name', '=', role_name), ('team_member', '=', self.env.uid)])

        access_type = "supportaccess"

        if not current_access:
            self.env['sudo_aws_access.main'].sudo().create({
                'ci': self,
                'team_member': self.env.user.id,
                'role_name': role_name,
                'access_type': access_type,
                'account_name': self.unique_asset_identifier
            })
            add_role_to_the_queue("sudo-ms-support-role", str(self.serial_asset_tag))

    # record.sudo().write({'sla_breaches_in': sla_breaches_in})

    def get_readonly_access(self):
        role_name = 'arn:aws:iam::' + str(self.serial_asset_tag) + ':role/sudo-ms-readonly-role'
        current_access = self.env['sudo_aws_access.main'].sudo().search(
            [('role_name', '=', role_name), ('team_member', '=', self.env.uid)])
        access_type = "readonlyaccess"

        if not current_access:
            self.env['sudo_aws_access.main'].sudo().create({
                'ci': self,
                'team_member': self.env.user.id,
                'role_name': role_name,
                'access_type': access_type,
                'account_name': self.unique_asset_identifier
            })
            add_role_to_the_queue("sudo-ms-readonly-role", str(self.serial_asset_tag))
# record.sudo().write({'sla_breaches_in': sla_breaches_in})
