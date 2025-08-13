# Copyright 2018 Eficent <http://www.eficent.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'


    def _systray_activities_data_query(self):
        """ Adiciona na query retornada, o JOIN e WHERE no local correto.

        Utiliza um dicionário com o termo a ser adicionado como valor e
        a posição da string que ele deverá ser adicionado.

        Returns:
            str: Query para busca de atividades ativas do usuário.
        """
        add_term_before = {
            'where': " JOIN mail_activity_type mat on act.activity_type_id = mat.id ",
            'group by': " AND act.done = False AND act.status = 'active' AND mat.show_on_plan_activities = True "
        }
        res = super(ResUsers, self)._systray_activities_data_query()

        for before, term in add_term_before.items():
            term_index = res.find(before.upper())
            res = res[:term_index] + term + res[term_index:]
        return res
