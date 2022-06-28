# -*- coding: utf-8 -*-
{
    'name': "SUDO AWS Access",

    'summary': """This module is design for giving AWS access to SUDO team""",

    'description': """
        This module is design for giving AWS access to SUDO team.
    """,

    'author': "Hameedullah Khan",
    'website': "http://www.sudoconsultants.com",
    'category': 'Extra Tools',
    'version': '0.9',
    'depends': ['base', 'sudo_cmdb'],
    'data': [
        'security/sudo_aws_access.xml',
        'security/ir.model.access.csv',

        'views/views.xml',
        'views/sudo_cmdb_access_approval.xml',
        'wizard/approver_reject_reason.xml',
    ],
}
