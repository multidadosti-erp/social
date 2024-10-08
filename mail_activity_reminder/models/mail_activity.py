# Copyright 2020 Brainbean Apps (https://brainbeanapps.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import datetime, time
from dateutil.relativedelta import relativedelta
from pytz import timezone, UTC
# from odoo.http import request
from odoo import _, api, fields, models, SUPERUSER_ID


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    next_reminder = fields.Datetime(
        string='Next reminder',
        compute='_compute_next_reminder',
        compute_sudo=True,
        store=True,
        index=True
    )

    last_reminder_local = fields.Datetime(
        string='Last reminder (local)',
    )

    deadline = fields.Datetime(
        string='Deadline',
        compute='_compute_deadline',
        compute_sudo=True,
        store=True,
        index=True
    )

    @api.model
    def _get_activities_to_remind_domain(self):
        """Hook for extensions"""
        return [
            ('next_reminder', '<=', fields.Datetime.now()),
            ('deadline', '>=', fields.Datetime.now()),
        ]

    @api.model
    def _get_activities_to_remind(self):
        return self.search(self._get_activities_to_remind_domain())

    @api.model
    def _process_reminders(self):
        activities = self._get_activities_to_remind()
        activities.action_remind()
        return activities

    @api.multi
    @api.depends(
        'user_id.tz',
        'activity_type_id.reminders',
        'deadline',
        'last_reminder_local',
    )
    def _compute_next_reminder(self):
        now = fields.Datetime.now()
        for activity in self:
            if activity.deadline < now:
                activity.next_reminder = None
                continue

            reminders = activity.activity_type_id._get_reminder_offsets()
            if not reminders:
                activity.next_reminder = None
                continue

            reminders.sort(reverse=True)
            tz = timezone(activity.user_id.sudo().tz or 'UTC')
            last_reminder_local = tz.localize(activity.last_reminder_local) if activity.last_reminder_local else None
            local_deadline = tz.localize(datetime.combine(activity.date_deadline, time.min)) # Schedule reminder based of beginning of day

            for reminder in reminders:
                next_reminder_local = local_deadline - relativedelta(days=reminder,)
                if not last_reminder_local or next_reminder_local > last_reminder_local:
                    break

            if last_reminder_local and next_reminder_local <= last_reminder_local:
                activity.next_reminder = None
                continue

            activity.next_reminder = next_reminder_local.astimezone(UTC).replace(tzinfo=None)

    @api.multi
    @api.depends('user_id.tz', 'date_deadline')
    def _compute_deadline(self):
        for activity in self:
            tz = timezone(activity.user_id.sudo().tz or 'UTC')
            activity.deadline = tz.localize(
                datetime.combine(activity.date_deadline, time.max)
            ).astimezone(UTC).replace(tzinfo=None)

    def _channel_notify_message(self, message_values):
        """ Envio de mensagem pelo chat do sistema, do BOT para
        o usuário atribuído à atividade, para notificar a
        atribuição à atividade.

        Args:
            message_values (dict): parâmetros para envio da
                mensagem.
        """
        # O channel deve estar presente nos valores da mensagem
        channel_id = message_values.pop('channel_id', False)
        if not channel_id:
            return

        channel_id.with_context(
            mail_create_nosubscribe=True, odoobot_do_not_answer=True
        ).sudo().message_post(**message_values)

    @api.multi
    def action_notify_message_channel(self):
        odoobot = self.env['res.users'].browse(SUPERUSER_ID)

        for activity in self:
            # Envia Msg
            channel_name = activity.user_id.name + ", " + odoobot.name
            channel_id = self.env['mail.channel'].search([
                ('name', '=', channel_name)
            ])

            if not channel_id:
                channel_dict = self.env['mail.channel'].sudo().channel_get([activity.user_id.partner_id.id])
                if channel_dict['id']:
                    channel_id = self.env['mail.channel'].browse(channel_dict['id'])

            action_id = self.env.ref('mail.mail_activity_action')
            url = '/web#id={0}&action={1}&model=mail.activity&view_type=form'.format(activity.id, action_id.id)
            body = (
                '<p> <b>{label_1} :</b> <i class="fa {icon}" style="color:red;"/> '
                '"{act_name}"</p> <p> <b>{label_2} :</b> {date_deadline}</p> <p> '
                '<b>{label_3} : {user_name}</b> </p> '
            ).format(**{
                'label_1': _('Activity Type'),
                'label_2': _('Date'),
                'label_3': _('Assigned By'),
                'icon': activity.activity_type_id.name,
                'act_name': activity.date_deadline,
                'date_deadline': activity.create_user_id.name,
                'user_name': activity.icon
            })

            if (activity.summary):
                body += '<p><b>{0}:</b> {1}</p>'.format(
                    _('Summary'), activity.summary)

            body += _('<a href="%s">Click to check detail activity </a> </br> ') % url

            values = {
                'channel_id': channel_id,
                'author_id': odoobot.id,
                'body': body,
                'message_type': 'comment',
                'subtype_id': self.env.ref('mail.mt_comment').id
            }
            self._channel_notify_message(values)

    @api.multi
    def action_notify(self):
        super().action_notify()

        utc_now = fields.Datetime.now().replace(tzinfo=UTC)
        for activity in self:
            reminders = activity.activity_type_id._get_reminder_offsets()
            if reminders:
                activity.action_notify_message_channel()

            if activity.last_reminder_local:
                continue

            tz = timezone(activity.user_id.sudo().tz or 'UTC')
            activity.last_reminder_local = utc_now.astimezone(tz).replace(tzinfo=None)

    @api.multi
    def action_remind(self):
        """ Action para Enviar Lembretes das Atividades
        """
        IrModel = self.env['ir.model']
        MailThread = self.env['mail.thread']

        message_activity_assigned = self.env.ref('mail.message_activity_assigned')
        utc_now = fields.Datetime.now().replace(tzinfo=UTC)

        for activity in self:
            tz = timezone(activity.user_id.sudo().tz or 'UTC')
            local_now = utc_now.astimezone(tz)
            model_description = IrModel._get(activity.res_model).display_name
            days_remaining = (activity.date_deadline - local_now.date()).days

            subject = _('%s: %s assigned to you, %d day(s) remaining') % (
                activity.res_name,
                activity.summary or activity.activity_type_id.name,
                days_remaining
            )

            body = message_activity_assigned.render(
                dict(activity=activity, model_description=model_description),
                engine='ir.qweb',
                minimal_qcontext=True,
            )

            # Envia e-mail
            MailThread.message_notify(
                partner_ids=activity.user_id.partner_id.ids,
                body=body,
                subject=subject,
                record_name=activity.res_name,
                model_description=model_description,
                notif_layout='mail.mail_notification_light',
            )

            # Envia Msg somente no dia
            if days_remaining == 0:
                activity.action_notify_message_channel()

            # Atualiza data para novo lembrete
            activity.last_reminder_local = local_now.replace(tzinfo=None)
