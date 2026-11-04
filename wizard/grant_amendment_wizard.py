# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GrantAmendmentWizard(models.TransientModel):
    """Wizard for creating grant amendments."""
    
    _name = 'ngo.grant.amendment.wizard'
    _description = 'Grant Amendment Wizard'
    
    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        readonly=True,
    )
    
    amendment_name = fields.Char(
        string='Amendment Name',
        required=True,
    )
    
    amendment_type = fields.Selection([
        ('budget_revision', 'Budget Revision'),
        ('extension', 'Extension (No-Cost)'),
        ('additional_funding', 'Additional Funding'),
        ('scope_change', 'Scope Change'),
        ('activity_revision', 'Activity Revision'),
        ('cost_sharing', 'Cost Sharing Change'),
        ('reporting_change', 'Reporting Change'),
        ('other', 'Other'),
    ],
        string='Amendment Type',
        required=True,
    )
    
    description = fields.Text(
        string='Description',
        required=True,
    )
    
    amount_change = fields.Float(
        string='Amount Change',
    )
    
    new_end_date = fields.Date(
        string='New End Date',
    )
    
    effective_date = fields.Date(
        string='Effective Date',
    )
    
    @api.constrains('new_end_date')
    def _check_new_end_date(self):
        """Validate new end date."""
        for wizard in self:
            if wizard.new_end_date and wizard.new_end_date <= wizard.grant_id.end_date:
                raise ValidationError(_('New End Date must be after the current Grant End Date.'))
    
    def action_create_amendment(self):
        """Create amendment from wizard."""
        self.ensure_one()
        
        amendment_vals = {
            'grant_id': self.grant_id.id,
            'amendment_name': self.amendment_name,
            'amendment_type': self.amendment_type,
            'description': self.description,
            'amount_change': self.amount_change,
            'new_end_date': self.new_end_date,
            'effective_date': self.effective_date,
            'original_end_date': self.grant_id.end_date,
            'state': 'draft',
        }
        
        amendment = self.env['ngo.grant.amendment'].create(amendment_vals)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grant Amendment'),
            'res_model': 'ngo.grant.amendment',
            'res_id': amendment.id,
            'view_mode': 'form',
            'target': 'current',
        }
