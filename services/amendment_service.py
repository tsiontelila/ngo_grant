# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import ValidationError


class AmendmentService(models.AbstractModel):
    """Service for Amendment business operations."""
    
    _name = 'ngo.grant.amendment.service'
    _description = 'NGO Amendment Service'
    
    @api.model
    def validate_amendment_for_approval(self, amendment_id):
        """Validate that an amendment can be approved."""
        amendment = self.env['ngo.grant.amendment'].browse(amendment_id)
        
        if amendment.state != 'under_review':
            raise ValidationError(_('Amendment must be in Under Review state before approval.'))
        
        if amendment.amendment_type == 'additional_funding' and not amendment.amount_change:
            raise ValidationError(_('Additional funding amendments must specify an amount change.'))
        
        if amendment.amendment_type == 'extension' and not amendment.new_end_date:
            raise ValidationError(_('Extension amendments must specify a new end date.'))
        
        return True
    
    @api.model
    def apply_amendment_to_grant(self, amendment_id):
        """Apply approved amendment to grant."""
        amendment = self.env['ngo.grant.amendment'].browse(amendment_id)
        grant = amendment.grant_id
        
        if amendment.amendment_type == 'additional_funding':
            grant.write({
                'approved_amount': amendment.new_approved_amount,
            })
        
        if amendment.amendment_type == 'extension':
            grant.write({
                'end_date': amendment.new_end_date,
            })
        
        if amendment.amendment_type == 'budget_revision':
            # Placeholder for integration with ngo_grant_budget module
            pass
        
        if amendment.amendment_type == 'scope_change':
            # Placeholder for integration with ngo_project module
            pass
        
        return True
    
    @api.model
    def get_amendment_history(self, grant_id):
        """Get amendment history for a grant."""
        grant = self.env['ngo.grant'].browse(grant_id)
        return grant.amendment_ids.sorted('amendment_date')
    
    @api.model
    def calculate_amendment_impact(self, amendment_id):
        """Calculate the impact of an amendment."""
        amendment = self.env['ngo.grant.amendment'].browse(amendment_id)
        
        impact = {
            'type': amendment.amendment_type,
            'amount_change': amendment.amount_change,
            'new_approved_amount': amendment.new_approved_amount,
            'extension_days': amendment.extension_days,
            'new_end_date': amendment.new_end_date,
        }
        
        return impact
