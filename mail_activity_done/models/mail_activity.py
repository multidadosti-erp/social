# Copyright 2018 Eficent <http://www.eficent.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
from odoo import api, fields, models, _
from datetime import date
from dateutil.relativedelta import relativedelta


class MailActivity(models.Model):

    _inherit = "mail.activity"

    active = fields.Boolean(
        default=True,
    )

    done = fields.Boolean(
        default=False,
    )

    state = fields.Selection(
        selection_add=[("done", "Done")],
        store=False,
        compute="_compute_state",
        search="_search_state",
    )

    date_done = fields.Date(
        "Completed Date",
        index=True,
        readonly=True,
    )

    status = fields.Selection(
        selection=[
            ("active", "Active"),
            ("canceled", "Canceled"),
            ("completed", "Completed"),
            ('reserved', 'Reserved'),
        ],
        default="active",
    )

    type_id_show_on_plan_activities = fields.Boolean(
        related="activity_type_id.show_on_plan_activities",
    )

    start = fields.Datetime(
        index=True,
        track_visibility="onchange",
    )  # Campos para Migrar no Calendar Event

    stop = fields.Datetime(
        index=True,
        track_visibility="onchange",
    )  # Campos para Migrar no Calendar Event

    duration = fields.Float()  # Campos para Migrar no Calendar Event

    @api.onchange("start")
    def _onchange_start(self):
        """Mantém o campo 'date_deadline' atualizado com o start
        e o stop maior que o start.
        """
        start = self.start

        if start:
            self.date_deadline = start.date()
            if self.stop and self.stop < start:
                self.stop = start + relativedelta(hours=1)
                return {
                    "warning": {
                        "title": _("Warning"),
                        "message": _("Stop time must be greather than start time."),
                    }
                }

    @api.onchange("stop")
    def _onchange_stop(self):
        """Mantém stop maior que start"""
        start, stop = self.start, self.stop

        if (start and stop) and stop < start:
            self.stop = start + relativedelta(hours=1)
            return {
                "warning": {
                    "title": _("Warning"),
                    "message": _("Stop time must be greather than start time."),
                }
            }

    def _search_state(self, operator, operand):
        """Método para Pesquisar o Campo State que é computed

        Returns:
            domain: Lista dos Ids a Mostrar
        """
        today_default = date.today()

        if operand == "done":
            domain = [("done", operator, True)]
        elif operand == "overdue":
            if operator == "=":
                domain = [("date_deadline", "<", today_default)]
            else:
                domain = [("date_deadline", ">=", today_default)]
        elif operand == "today":
            if operator == "=":
                domain = [("date_deadline", "=", today_default)]
            else:
                domain = [("date_deadline", "!=", today_default)]
        elif operand == "planned":
            if operator == "=":
                domain = [("date_deadline", ">", today_default)]
            else:
                domain = [("date_deadline", "<=", today_default)]
        else:
            domain = [("1", "=", "0")]

        ids = self.search(domain).ids

        return [("id", "in", ids)]

    @api.multi
    def _get_activity_data_basic_domain(self, res_model):
        """ Adicionado filtro para obter somente atividades ativas.

        Args:
            res_model (str): model a encontrar atividades

        Returns:
            list: domain para busca de atividades
        """
        res = super(MailActivity, self)._get_activity_data_basic_domain(res_model)
        res.extend([("active", "=", True), ("done", "=", False)])
        return res

    @api.depends("date_deadline", "done")
    def _compute_state(self):
        super(MailActivity, self)._compute_state()
        for record in self.filtered(lambda activity: activity.done):
            record.state = "done"


class MailActivityMixin(models.AbstractModel):

    _inherit = "mail.activity.mixin"

    activity_ids = fields.One2many(
        domain=lambda self: [
            ("res_model", "=", self._name),
            ("active", "=", True),
            ("done", "=", False),
            ("type_id_show_on_plan_activities", "=", True),
        ]
    )

    def get_activities_states(self):
        """Sobrescreve método do Core para adicionar
           Filtro DONE == False (não Concluido)

        Returns:
            [list]: Ids das Atividades por State
        """
        return self.activity_ids.filtered(
            lambda x: not x.done and x.status == "active"
        ).mapped("state")

    def _get_activity_where_statement(self):
        """Adiciona condição em cláusula where de sql utilizado em
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
        """Atualiza método search, para considerar apenas atividades que
        ainda não foram concluídas.

        Args:
            operator (str): tipo de operador comparativo
            operand (any): qualquer valor que está sendo comparado

        Returns:
            list: domain do search
        """
        res = super(MailActivityMixin, self)._search_activity_date_deadline(
            operator, operand
        )
        res.append(("activity_ids.done", "=", False))
        return res
