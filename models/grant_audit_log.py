# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class NgoGrantAuditLog(models.Model):
    """Immutable audit trail for NGO Grant changes."""

    _name = 'ngo.grant.audit.log'
    _description = 'NGO Grant Audit Trail Log'
    _order = 'timestamp desc, id desc'

    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        ondelete='cascade',
        index=True,
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )
    
    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    
    model_name = fields.Char(
        string='Model',
        required=True,
        readonly=True,
    )
    
    res_id = fields.Integer(
        string='Record ID',
        required=True,
        readonly=True,
    )
    
    field_name = fields.Char(
        string='Field Name',
        required=True,
        readonly=True,
    )
    
    field_description = fields.Char(
        string='Field Label',
        readonly=True,
    )
    
    old_value = fields.Text(
        string='Old Value',
        readonly=True,
    )
    
    new_value = fields.Text(
        string='New Value',
        readonly=True,
    )
    
    action_type = fields.Selection([
        ('create', 'Create'),
        ('write', 'Update'),
        ('unlink', 'Delete'),
        ('action', 'Workflow Action'),
    ], string='Action Type', default='write', required=True, readonly=True)

    def write(self, vals):
        raise UserError(_("Audit trail records are immutable and cannot be modified."))

    def unlink(self):
        raise UserError(_("Audit trail records are immutable and cannot be deleted."))
