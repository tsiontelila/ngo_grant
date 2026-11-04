# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


class ReportingService(models.AbstractModel):
    """Service for Reporting Schedule business operations."""
    
    _name = 'ngo.grant.reporting.service'
    _description = 'NGO Reporting Service'
    
    @api.model
    def get_overdue_reports(self, grant_id=None):
        """Get overdue reports, optionally filtered by grant."""
        today = fields.Date.today()
        domain = [
            ('report_date', '<', today),
            ('state', 'in', ['draft', 'scheduled', 'in_preparation', 'submitted', 'under_donor_review']),
        ]
        if grant_id:
            domain.append(('grant_id', '=', grant_id))
        return self.env['ngo.grant.reporting.schedule'].search(domain)
    
    @api.model
    def get_upcoming_reports(self, grant_id=None, days=30):
        """Get upcoming reports due within specified days."""
        today = fields.Date.today()
        upcoming_date = today + relativedelta(days=days)
        domain = [
            ('report_date', '<=', upcoming_date),
            ('report_date', '>=', today),
            ('state', 'in', ['draft', 'scheduled', 'in_preparation', 'submitted', 'under_donor_review']),
        ]
        if grant_id:
            domain.append(('grant_id', '=', grant_id))
        return self.env['ngo.grant.reporting.schedule'].search(domain)
    
    @api.model
    def send_report_reminders(self):
        """Send reminders for upcoming reports."""
        upcoming = self.get_upcoming_reports(days=7)
        for report in upcoming:
            if not report.reminder_sent:
                report.action_send_reminder()
    
    @api.model
    def check_reporting_status(self, grant_id):
        """Check overall reporting status for a grant."""
        grant = self.env['ngo.grant'].browse(grant_id)
        schedules = grant.reporting_schedule_ids
        
        total = len(schedules)
        draft = len(schedules.filtered(lambda s: s.state == 'draft'))
        scheduled = len(schedules.filtered(lambda s: s.state == 'scheduled'))
        in_preparation = len(schedules.filtered(lambda s: s.state == 'in_preparation'))
        submitted = len(schedules.filtered(lambda s: s.state == 'submitted'))
        under_donor_review = len(schedules.filtered(lambda s: s.state == 'under_donor_review'))
        accepted = len(schedules.filtered(lambda s: s.state == 'accepted'))
        completed = len(schedules.filtered(lambda s: s.state == 'completed'))
        overdue = len(schedules.filtered(lambda s: s.state == 'overdue'))
        
        return {
            'total': total,
            'draft': draft,
            'scheduled': scheduled,
            'in_preparation': in_preparation,
            'submitted': submitted,
            'under_donor_review': under_donor_review,
            'accepted': accepted,
            'completed': completed,
            'overdue': overdue,
            'completion_rate': (completed / total * 100) if total > 0 else 100,
        }
    
    @api.model
    def generate_reporting_calendar(self, grant_id):
        """Generate reporting calendar for a grant."""
        self.env['ngo.grant.reporting.schedule'].generate_calendar(grant_id)
    
    @api.model
    def get_reporting_summary(self, grant_id):
        """Get reporting summary for dashboard."""
        grant = self.env['ngo.grant'].browse(grant_id)
        status = self.check_reporting_status(grant_id)
        
        return {
            'grant': grant.grant_number,
            'status': status,
            'next_due': self.get_upcoming_reports(grant_id, days=30)[:1].report_date if self.get_upcoming_reports(grant_id, days=30) else None,
        }
