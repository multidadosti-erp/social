from odoo import fields, models


class MailActivityType(models.Model):
    _inherit = 'mail.activity.type'

    show_on_plan_activities = fields.Boolean(
        string='Show on Plan Activities',
        default=True
    )
