# Copyright 2018 David Juaneda - <djuaneda@sdi.es>
# Copyright 2018 Eficent Business and IT Consulting Services, S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, models, fields, SUPERUSER_ID
from datetime import datetime
from dateutil.relativedelta import relativedelta


class MailActivity(models.Model):
    _inherit = "mail.activity"

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        help="Used to diplay a name for the activity based on partner's name.",
    )

    color = fields.Integer(
        string="Color Index",
    )

    res_model_id_name = fields.Char(
        related="res_model_id.name",
        string="Origin",
        readonly=True,
    )

    calendar_event_id_duration = fields.Float(
        string="Meeting Duration",
        related="calendar_event_id.duration",
        readonly=True,
    )

    calendar_event_id_start = fields.Datetime(
        string="Meeting Start",
        related="calendar_event_id.start",
        readonly=True,
    )

    calendar_event_id_stop = fields.Datetime(
        string="Meeting Stop",
        related="calendar_event_id.stop",
        readonly=True,
    )

    calendar_event_id_partner_ids = fields.Many2many(
        related="calendar_event_id.partner_ids",
        readonly=True,
    )

    location = fields.Char()  # Campos para Migrar no Calendar Event

    event_datetime_start = (
        fields.Datetime(  # Campos que devem ser related do calendar.event
            string="Event Start Time"
        )
    )

    event_datetime_stop = (
        fields.Datetime(  # Campos que devem ser related do calendar.event
            string="Event Stop Time"
        )
    )

    event_duration = fields.Float(  # Campos que devem ser related do calendar.event
        "Event Duration"
    )

    event_location = fields.Char(  # Campos que devem ser related do calendar.event
        "Event Location"
    )

    datetime_state = fields.Selection(
        [
            ("overdue", "Overdue"),
            ("today", "Today"),
            ("planned", "Planned"),
            ("done", "Done"),
        ],
        string="Time State",
        compute="_compute_datetime_state",
    )

    def get_display_name(self):
        return self.res_name

    def _compute_display_name(self):
        """Compute no campo que será usado para ser apresentado como o
        nome da atividade.
        """
        for rec in self:
            rec.display_name = rec.get_display_name()

    @api.multi
    def open_origin(self):
        self.ensure_one()
        if "sale.order" in self.res_model:
            res_model = "sale.order"
        else:
            res_model = self.res_model

        model_id = self.env["ir.model"].sudo().search([("model", "=", res_model)])

        if model_id:
            group_ids = ", ".join(
                str(x) for x in model_id.access_ids.mapped("group_id").ids
            )
        else:
            group_ids = False

        if self.user_has_groups(groups=False, group_ids=group_ids):
            vid = self.env[self.res_model].browse(self.res_id).get_formview_id()
            response = {
                "type": "ir.actions.act_window",
                "res_model": self.res_model,
                "view_mode": "form",
                "res_id": self.res_id,
                "target": "current",
                "flags": {"form": {"action_buttons": False}},
                "views": [(vid, "form")],
            }
            return response
        else:
            return False

    @api.model
    def action_activities_board(self):
        action = self.env.ref("mail_activity_board.open_boards_activities").read()[0]
        return action

    @api.model
    def _find_allowed_model_wise(self, doc_model, doc_dict):
        doc_ids = list(doc_dict)
        allowed_doc_ids = (
            self.env[doc_model]
            .with_context(active_test=False)
            .search([("id", "in", doc_ids)])
            .ids
        )
        return set(
            [
                message_id
                for allowed_doc_id in allowed_doc_ids
                for message_id in doc_dict[allowed_doc_id]
            ]
        )

    @api.model
    def _find_allowed_doc_ids(self, model_ids):
        ir_model_access_model = self.env["ir.model.access"]
        allowed_ids = set()
        for doc_model, doc_dict in model_ids.items():
            if not ir_model_access_model.check(doc_model, "read", False):
                continue
            allowed_ids |= self._find_allowed_model_wise(doc_model, doc_dict)
        return allowed_ids

    @api.model
    def _search(
        self,
        args,
        offset=0,
        limit=None,
        order=None,
        count=False,
        access_rights_uid=None,
    ):
        # Rules do not apply to administrator
        if self._uid == SUPERUSER_ID:
            return super(MailActivity, self)._search(
                args,
                offset=offset,
                limit=limit,
                order=order,
                count=count,
                access_rights_uid=access_rights_uid,
            )

        ids = super(MailActivity, self)._search(
            args,
            offset=offset,
            limit=limit,
            order=order,
            count=False,
            access_rights_uid=access_rights_uid,
        )
        if not ids and count:
            return 0
        elif not ids:
            return ids

        # check read access rights before checking the actual rules
        super(
            MailActivity, self.sudo(access_rights_uid or self._uid)
        ).check_access_rights("read")

        model_ids = {}

        self._cr.execute(
            """
            SELECT DISTINCT a.id, im.id, im.model, a.res_id
            FROM "%s" a
            LEFT JOIN ir_model im ON im.id = a.res_model_id
            WHERE a.id = ANY (%%(ids)s)"""
            % self._table,
            dict(ids=ids),
        )
        for a_id, ir_model_id, model, model_id in self._cr.fetchall():
            model_ids.setdefault(model, {}).setdefault(model_id, set()).add(a_id)

        allowed_ids = self._find_allowed_doc_ids(model_ids)

        final_ids = allowed_ids

        if count:
            return len(final_ids)
        else:
            # re-construct a list based on ids, because set didn't keep order
            id_list = [a_id for a_id in ids if a_id in final_ids]
            return id_list

    def _compute_datetime_state(self):
        """Obtém o state baseado no horário de ínicio da
        atividade, e nao somente no dia

        Returns:
            str: State do horario da atividade
        """
        for rec in self:
            status = "planned"
            state = rec.state
            start = rec.start or rec.calendar_event_id_start
            if start:
                if state in ["overdue", "done"]:
                    status = state
                elif rec.state == "today":
                    now = datetime.now()
                    if start > now + relativedelta(hours=1):
                        status = "planned"
                    elif start >= now:
                        status = "today"
                    else:
                        status = "overdue"
            rec.datetime_state = status

    def get_calendar_event_vals(self):
        """Obtém os valores para a criação do evento de
        calendário

        Returns:
            dict: Valores para a criação do evento
        """
        stop = self.stop
        if not stop:
            stop = self.start + relativedelta(hours=1)
        return {"user_id": self.user_id.id, "start": self.start, "stop": stop}

    @api.multi
    def action_create_calendar_event(self):
        """Caso o campo start tenha sido populado na atividade,
        ao abrir o calendário, o registro da reunião já terá sido
        criado e seu form abrirá.

        Returns:
            dict: Valores da Action de Eventos do Calendário
        """
        res = super().action_create_calendar_event()

        CalendarEvent = self.env["calendar.event"].with_context(res["context"])
        if self.start or self.calendar_event_id:
            if not self.calendar_event_id:
                # Cria evento do calendário e abre o form
                # dele direto caso tenha sido criado.
                try:
                    calendar_event = CalendarEvent.create(
                        self.get_calendar_event_vals()
                    )
                except:
                    calendar_event = False
            else:
                # abre o form do evento do calendário relacionado
                calendar_event = self.calendar_event_id

            if calendar_event:
                res["res_id"] = calendar_event.id
                res["view_mode"] = "form,tree,calendar"
                res["views"].reverse()

        return res

    def write(self, values):
        """Atualiza valores do start e stop do evento
        do calendário

        Args:
            values (dict): valores de atualização da atividade
        Returns:
            bool: Resultado da atualização
        """
        res = super(MailActivity, self).write(values)
        for rec in self:
            if self._context.get("calendar_from_activity"):
                if rec.calendar_event_id:
                    if "start" in values:
                        self.calendar_event_id.start = values["start"]
                    if "stop" in values:
                        self.calendar_event_id.start = values["stop"]
        return res
