# Copyright 2018 Eficent <http://www.eficent.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
from odoo import api, fields, models, _


class MailActivity(models.Model):

    _inherit = 'mail.activity'

    active = fields.Boolean(default=True)
    done = fields.Boolean(default=False)
    state = fields.Selection(selection_add=[
        ('done', 'Done')], compute='_compute_state')
    date_done = fields.Date(
        'Completed Date', index=True, readonly=True,
    )
    status = fields.Selection(
        selection=[('active', _('Active')),],
        default='active')

    @api.depends('date_deadline', 'done')
    def _compute_state(self):
        super(MailActivity, self)._compute_state()
        for record in self.filtered(lambda activity: activity.done):
            record.state = 'done'


class MailActivityMixin(models.AbstractModel):

    _inherit = 'mail.activity.mixin'

    activity_ids = fields.One2many(
        domain=lambda self: [('res_model', '=', self._name),
                             ('active', '=', True)])


    def get_activities_states(self):
        """Sobrescreve método do Core para adicionar
           Filtro DONE == False (não Concluido)

        Returns:
            [list]: Ids das Atividades por State
        """
        return self.activity_ids.filtered(lambda x: x.done == False).mapped('state')

    def _search_activity_date_deadline(self, operator, operand):
        if operator == '=' and not operand:
            return [('activity_ids', '=', False)]
        return [
            ('activity_ids.date_deadline', operator, operand),
            ('activity_ids.done', '=', False)
        ]
