# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class GrantService(models.AbstractModel):
    """Service for Grant business operations."""
    
    _name = 'ngo.grant.service'
    _description = 'NGO Grant Service'
    
    @api.model
    def validate_grant_for_activation(self, grant_id):
        """Validate that a grant can be activated."""
        grant = self.env['ngo.grant'].browse(grant_id)
        
        if not grant.donor_line_ids:
            raise ValidationError(_('Grant must have at least one donor allocation before activation.'))
        
        total_amount = sum(grant.donor_line_ids.mapped('contribution_amount'))
        if abs(total_amount - grant.approved_amount) > 0.01:
            raise ValidationError(_('Total donor contributions must equal the approved grant amount.'))
        
        total_percentage = sum(grant.donor_line_ids.mapped('contribution_percentage'))
        if abs(total_percentage - 100) > 0.01:
            raise ValidationError(_('Total donor contribution percentage must equal 100%.'))
        
        if not grant.start_date or not grant.end_date:
            raise ValidationError(_('Grant must have start and end dates before activation.'))
        
        return True
    
    @api.model
    def calculate_remaining_budget(self, grant_id):
        """Calculate remaining budget for a grant."""
        grant = self.env['ngo.grant'].browse(grant_id)
        # Placeholder for integration with ngo_grant_budget module
        return grant.approved_amount - grant.disbursed_amount
    
    @api.model
    def get_grant_statistics(self, grant_id):
        """Get comprehensive grant statistics."""
        grant = self.env['ngo.grant'].browse(grant_id)
        
        return {
            'grant_number': grant.grant_number,
            'grant_name': grant.grant_name,
            'state': grant.state,
            'approved_amount': grant.approved_amount,
            'disbursed_amount': grant.disbursed_amount,
            'remaining_amount': grant.remaining_amount,
            'project_count': grant.project_count,
            'amendment_count': grant.amendment_count,
            'compliance_count': grant.compliance_count,
            'reporting_schedule_count': grant.reporting_schedule_count,
            'donor_count': len(grant.donor_line_ids),
            'start_date': grant.start_date,
            'end_date': grant.end_date,
        }
    
    @api.model
    def check_grant_expiry(self):
        """Check for grants approaching expiry and send notifications."""
        today = fields.Date.today()
        warning_date = today + relativedelta(months=3)
        
        expiring_grants = self.env['ngo.grant'].search([
            ('end_date', '<=', warning_date),
            ('end_date', '>=', today),
            ('state', '=', 'active'),
        ])
        
        for grant in expiring_grants:
            grant.message_post(
                body=_('Grant is expiring on %(date)s') % {'date': grant.end_date}
            )
            # Send notification to grant manager
            # Implementation depends on ngo_notification module
    
    @api.model
    def generate_grant_report(self, grant_id):
        """Generate comprehensive grant report."""
        grant = self.env['ngo.grant'].browse(grant_id)
        
        # Placeholder for report generation
        # This will integrate with ngo_reporting module
        return {
            'grant': grant.grant_number,
            'donors': grant.donor_line_ids.mapped('donor_id.name'),
            'projects': grant.project_ids.mapped('project_id.name'),
            'amendments': grant.amendment_ids.mapped('amendment_number'),
        }
