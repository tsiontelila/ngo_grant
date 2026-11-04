# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from dateutil.relativedelta import relativedelta


class ComplianceService(models.AbstractModel):
    """Service for Compliance business operations."""
    
    _name = 'ngo.grant.compliance.service'
    _description = 'NGO Compliance Service'
    
    @api.model
    def get_overdue_compliance(self, grant_id=None):
        """Get overdue compliance items, optionally filtered by grant."""
        today = fields.Date.today()
        domain = [
            ('due_date', '<', today),
            ('state', 'in', ['draft', 'assigned', 'in_progress', 'evidence_submitted']),
        ]
        if grant_id:
            domain.append(('grant_id', '=', grant_id))
        return self.env['ngo.grant.compliance'].search(domain)
    
    @api.model
    def get_upcoming_compliance(self, grant_id=None, days=30):
        """Get upcoming compliance items due within specified days."""
        today = fields.Date.today()
        upcoming_date = today + relativedelta(days=days)
        domain = [
            ('due_date', '<=', upcoming_date),
            ('due_date', '>=', today),
            ('state', 'in', ['draft', 'assigned', 'in_progress', 'evidence_submitted']),
        ]
        if grant_id:
            domain.append(('grant_id', '=', grant_id))
        return self.env['ngo.grant.compliance'].search(domain)
    
    @api.model
    def send_compliance_reminders(self):
        """Send reminders for upcoming compliance items."""
        upcoming = self.get_upcoming_compliance(days=7)
        for item in upcoming:
            if not item.reminder_sent:
                item.action_send_reminder()
    
    @api.model
    def check_compliance_status(self, grant_id):
        """Check overall compliance status for a grant."""
        grant = self.env['ngo.grant'].browse(grant_id)
        compliances = grant.compliance_ids
        
        total = len(compliances)
        draft = len(compliances.filtered(lambda c: c.state == 'draft'))
        assigned = len(compliances.filtered(lambda c: c.state == 'assigned'))
        in_progress = len(compliances.filtered(lambda c: c.state == 'in_progress'))
        evidence_submitted = len(compliances.filtered(lambda c: c.state == 'evidence_submitted'))
        under_verification = len(compliances.filtered(lambda c: c.state == 'under_verification'))
        completed = len(compliances.filtered(lambda c: c.state == 'completed'))
        overdue = len(compliances.filtered(lambda c: c.state == 'overdue'))
        
        return {
            'total': total,
            'draft': draft,
            'assigned': assigned,
            'in_progress': in_progress,
            'evidence_submitted': evidence_submitted,
            'under_verification': under_verification,
            'completed': completed,
            'overdue': overdue,
            'completion_rate': (completed / total * 100) if total > 0 else 100,
        }
    
    @api.model
    def generate_compliance_report(self, grant_id):
        """Generate compliance report for a grant."""
        grant = self.env['ngo.grant'].browse(grant_id)
        status = self.check_compliance_status(grant_id)
        
        return {
            'grant': grant.grant_number,
            'status': status,
            'compliances': grant.compliance_ids.mapped('name'),
        }
