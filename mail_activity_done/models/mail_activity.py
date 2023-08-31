# Copyright 2018 Eficent <http://www.eficent.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
from odoo import api, fields, models, _


class MailActivity(models.Model):

    _inherit = 'mail.activity'

    active = fields.Boolean(
        default=True)

    done = fields.Boolean(
        default=False)

    state = fields.Selection(
        selection_add=[
            ('done', 'Done')
        ],
        compute='_compute_state')

    date_done = fields.Date(
        'Completed Date',
        index=True,
        readonly=True,
    )

    status = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('canceled', 'Canceled'),
            ('completed', 'Completed'),
        ],
        default='active')

    type_id_show_on_plan_activities = fields.Boolean(
        related='activity_type_id.show_on_plan_activities')

    @api.depends('date_deadline', 'done')
    def _compute_state(self):
        super(MailActivity, self)._compute_state()
        for record in self.filtered(lambda activity: activity.done):
            record.state = 'done'


class MailActivityMixin(models.AbstractModel):

    _inherit = 'mail.activity.mixin'

    activity_ids = fields.One2many(
        domain=lambda self: [
            ('res_model', '=', self._name),
            ('active', '=', True),
            ('done', '=', False),
            ('type_id_show_on_plan_activities', '=', True)
        ]
    )

    def get_activities_states(self):
        """Sobrescreve método do Core para adicionar
           Filtro DONE == False (não Concluido)

        Returns:
            [list]: Ids das Atividades por State
        """
        return self.activity_ids.filtered(
                lambda x: not x.done and x.status == 'active'
            ).mapped('state')

    def _get_activity_where_statement(self):
        """ Adiciona condição em cláusula where de sql utilizado em
        função do core para obter atividades atrasadas. Adiciona as
        condições para pegar apenas atividades que não foram concluídas
        (done = False) e atividades que estão ativas (status = 'active').

        Returns:
            str: Condições do WHERE executado na tabela 'mail.activity'
        """
        res = super(MailActivityMixin, self)._get_activity_where_statement()
        res += "AND done = False AND status = 'active' "
        return res

    def _search_activity_date_deadline(self, operator, operand):
        """ Atualiza método search, para considerar apenas atividades que
        ainda não foram concluídas.

        Args:
            operator (str): tipo de operador comparativo
            operand (any): qualquer valor que está sendo comparado

        Returns:
            list: domain do search
        """
        res = super(MailActivityMixin, self)._search_activity_date_deadline(operator, operand)
        res.append(('activity_ids.done', '=', False))
        return res
