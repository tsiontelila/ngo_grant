# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError
from dateutil.relativedelta import relativedelta
from .workflow_access import check_cancellation_access, check_reset_access


class NgoGrantReportingSchedule(models.Model):
    """NGO Grant Reporting Schedule model.
    
    Defines recurring reporting obligations such as Monthly, Quarterly, Semi-Annual, Annual, and Final Report.
    The schedule can drive automated reminders, dashboard alerts, and reporting workflows.
    """
    
    _name = 'ngo.grant.reporting.schedule'
    _description = 'NGO Grant Reporting Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ngo.cancellation.access.mixin']
    _order = 'report_date'
    _rec_name = 'name'
    
    # References
    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Associated grant',
    )
    subgrant_id = fields.Many2one(
        'ngo.subgrant', string='Subgrant', ondelete='cascade', tracking=True,
        help='Optional subgrant this reporting schedule applies to',
    )
    
    # Identification
    name = fields.Char(
        string='Report Name',
        required=True,
        tracking=True,
        help='Report name',
    )
    
    report_type = fields.Selection([
        ('financial', 'Financial Report'),
        ('narrative', 'Narrative Report'),
        ('procurement', 'Procurement Report'),
        ('monitoring', 'Monitoring Report'),
        ('meal', 'MEAL Report'),
        ('audit', 'Audit Report'),
        ('inventory', 'Inventory Report'),
        ('asset', 'Asset Report'),
        ('completion', 'Project Completion Report'),
        ('ad_hoc', 'Ad-hoc Report'),
    ],
        string='Report Type',
        required=True,
        tracking=True,
        help='Type of report',
    )
    
    reporting_frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('ad_hoc', 'Ad-hoc'),
    ],
        string='Reporting Frequency',
        tracking=True,
        help='Frequency of this report',
    )
    
    # Dates
    report_period_start = fields.Date(
        string='Period Start',
        required=True,
        tracking=True,
        help='Start date of reporting period',
    )
    
    report_period_end = fields.Date(
        string='Period End',
        required=True,
        tracking=True,
        help='End date of reporting period',
    )
    
    report_date = fields.Date(
        string='Report Due Date',
        required=True,
        tracking=True,
        help='Date when report is due',
    )

    @api.onchange('grant_id')
    def _onchange_grant_id_subgrant(self):
        if self.subgrant_id and self.subgrant_id.grant_id != self.grant_id:
            self.subgrant_id = False

    @api.onchange('subgrant_id')
    def _onchange_subgrant_id_grant(self):
        if self.subgrant_id:
            self.grant_id = self.subgrant_id.grant_id

    @api.constrains('grant_id', 'subgrant_id')
    def _check_subgrant_parent(self):
        for schedule in self:
            if schedule.subgrant_id and schedule.subgrant_id.grant_id != schedule.grant_id:
                raise ValidationError(_('The selected subgrant must belong to the selected grant.'))
    
    submitted_date = fields.Date(
        string='Submitted Date',
        tracking=True,
        help='Date when report was submitted',
    )
    
    donor_response_date = fields.Date(
        string='Donor Response Date',
        tracking=True,
        help='Date when donor responded to the report',
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('in_preparation', 'In Preparation'),
        ('submitted', 'Submitted'),
        ('under_donor_review', 'Under Donor Review'),
        ('accepted', 'Accepted'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        help='Report status',
    )
    
    # Responsibility
    donor_contact_id = fields.Many2one(
        'ngo.grant.contact',
        string='Donor Contact',
        tracking=True,
        help='Donor contact for this report',
    )
    
    responsible_employee_id = fields.Many2one(
        'hr.employee',
        string='Responsible Employee',
        tracking=True,
        help='Employee responsible for this report',
    )
    
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsible User',
        tracking=True,
        help='User responsible for this report',
    )
    
    document_id = fields.Many2one(
        'ngo.grant.document',
        string='Report Document',
        tracking=True,
        help='Document linked to this report',
    )
    
    # Review
    submitted_by = fields.Many2one(
        'res.users',
        string='Submitted By',
        tracking=True,
        help='User who submitted the report',
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        tracking=True,
        help='User who approved the report',
    )
    
    donor_feedback = fields.Text(
        string='Donor Feedback',
        help='Feedback from donor',
    )
    
    # Details
    description = fields.Text(
        string='Description',
        help='Report description',
    )
    
    requirements = fields.Text(
        string='Requirements',
        help='Specific requirements for this report',
    )
    
    # Documents
    document_ids = fields.One2many(
        'ngo.grant.document',
        'reporting_schedule_id',
        string='Report Documents',
        help='Documents submitted for this report',
    )
    
    # Monitoring
    reminder_sent = fields.Boolean(
        string='Reminder Sent',
        default=False,
        help='Whether reminder notification has been sent',
    )
    
    reminder_count = fields.Integer(
        string='Reminder Count',
        default=0,
        help='Number of reminders sent',
    )
    
    is_overdue = fields.Boolean(
        string='Is Overdue',
        compute='_compute_is_overdue',
        store=True,
        help='Whether report is overdue',
    )
    
    days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_days_overdue',
        store=True,
        help='Days report is overdue',
    )
    
    days_until_due = fields.Integer(
        string='Days Until Due',
        compute='_compute_days_until_due',
        store=True,
        help='Days until report is due',
    )
    
    # Donor Reference
    donor_reference = fields.Char(
        string='Donor Reference',
        help='Reference number from donor',
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional notes',
    )
    
    @api.constrains('grant_id', 'name')
    def _check_name_unique_per_grant(self):
        """Ensure report name is unique per grant."""
        for schedule in self:
            if schedule.grant_id and schedule.name:
                existing = self.search([
                    ('grant_id', '=', schedule.grant_id.id),
                    ('name', '=', schedule.name),
                    ('id', '!=', schedule.id),
                ])
                if existing:
                    raise ValidationError(_('Report name must be unique per grant!'))
    
    @api.depends('report_date', 'submitted_date')
    def _compute_is_overdue(self):
        """Compute whether report is overdue."""
        for schedule in self:
            if schedule.report_date and not schedule.submitted_date:
                schedule.is_overdue = schedule.report_date < fields.Date.today()
            else:
                schedule.is_overdue = False
    
    @api.depends('report_date', 'submitted_date')
    def _compute_days_overdue(self):
        """Compute days overdue."""
        for schedule in self:
            if schedule.report_date and not schedule.submitted_date and schedule.report_date < fields.Date.today():
                schedule.days_overdue = (fields.Date.today() - schedule.report_date).days
            else:
                schedule.days_overdue = 0
    
    @api.depends('report_date', 'submitted_date')
    def _compute_days_until_due(self):
        """Compute days until due."""
        for schedule in self:
            if schedule.report_date and not schedule.submitted_date and schedule.report_date >= fields.Date.today():
                schedule.days_until_due = (schedule.report_date - fields.Date.today()).days
            else:
                schedule.days_until_due = 0
    
    @api.constrains('report_period_start', 'report_period_end')
    def _check_period_dates(self):
        """Validate period dates."""
        for schedule in self:
            if schedule.report_period_start and schedule.report_period_end:
                if schedule.report_period_start > schedule.report_period_end:
                    raise ValidationError(_('Period Start must be before Period End.'))
    
    @api.constrains('report_period_end', 'report_date')
    def _check_report_date(self):
        """Validate report date."""
        for schedule in self:
            if schedule.report_period_end and schedule.report_date:
                if schedule.report_date < schedule.report_period_end:
                    raise ValidationError(_('Report Due Date cannot be before Period End.'))
    
    @api.constrains('submitted_date', 'report_date')
    def _check_submitted_date(self):
        """Validate submitted date."""
        for schedule in self:
            if schedule.submitted_date and schedule.report_date:
                if schedule.submitted_date > schedule.report_date:
                    # Allow but flag as late
                    pass
    
    # Business Methods
    def write(self, vals):
        operational_fields = {'state', 'reminder_sent', 'reminder_count', 'is_overdue', 'days_overdue', 'days_until_due'}
        locked_states = ('accepted', 'completed', 'cancelled')
        if not self.env.su and 'state' in vals and vals['state'] != 'cancelled' and any(record.state in locked_states for record in self):
            raise AccessError(_('Approved reporting schedules cannot be changed until an administrator cancels them.'))
        if not self.env.su and set(vals) - operational_fields:
            if any(record.state in locked_states for record in self):
                raise AccessError(_('Approved reporting details are locked. An administrator must cancel the schedule before it can be reset and edited.'))
        return super().write(vals)

    def action_start(self):
        """Mark as in preparation."""
        self.write({'state': 'in_preparation'})
        self.message_post(body=_('Report marked as in preparation.'))
    
    def action_submit(self):
        """Submit report."""
        self.write({
            'state': 'submitted',
            'submitted_date': fields.Date.today(),
        })
        self.message_post(body=_('Report submitted.'))
    
    def action_approve(self):
        """Approve report."""
        self.write({'state': 'accepted'})
        self.message_post(body=_('Report accepted.'))
    
    def action_reject(self):
        """Reject report."""
        self.write({'state': 'rejected'})
        self.message_post(body=_('Report rejected.'))

    def action_cancel(self):
        check_cancellation_access(self)
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({'state': 'cancelled'})
        self.sudo().message_post(body=_('Reporting schedule cancelled.'))

    def action_reset_cancelled(self):
        check_reset_access(self)
        for record in self:
            if record.state != 'cancelled':
                raise ValidationError(_('Only cancelled reporting schedules can be reset to Draft.'))
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({
            'state': 'draft', 'submitted_date': False, 'submitted_by': False,
            'donor_response_date': False, 'approved_by': False,
        })
        self.sudo().message_post(body=_('Cancelled reporting schedule reset to Draft for revision.'))
    
    def action_waive(self):
        """Waive report."""
        self.write({'state': 'completed'})
        self.message_post(body=_('Report waived.'))
    
    def action_send_reminder(self):
        """Send reminder notification."""
        for schedule in self:
            schedule.write({
                'reminder_sent': True,
                'reminder_count': schedule.reminder_count + 1,
            })
            schedule.message_post(
                body=_('Reminder sent to %(user)s') % {'user': schedule.responsible_id.name if schedule.responsible_id else 'Responsible User'}
            )
            # Send email notification if responsible user is set
            if schedule.responsible_id:
                template = self.env.ref('ngo_grant.email_template_report_reminder', raise_if_not_found=False)
                if template:
                    # Repair legacy databases that still store the old
                    # expression instead of a valid language code.
                    if template.lang != 'en_US':
                        template.sudo().write({'lang': 'en_US'})
                    template.send_mail(schedule.id, force_send=True)
    
    @api.model
    def generate_calendar(self, grant_id):
        """Generate reporting calendar for a grant."""
        grant = self.env['ngo.grant'].browse(grant_id)
        if not grant:
            return
        
        # Clear existing schedules
        existing = self.search([('grant_id', '=', grant_id)])
        existing.unlink()
        
        start_date = grant.start_date
        end_date = grant.end_date
        
        # Generate schedules based on donor reporting frequency
        # This is a simplified version - actual implementation would be more sophisticated
        current_date = start_date
        sequence = 1
        
        while current_date <= end_date:
            # Create quarterly reports
            quarter_end = current_date + relativedelta(months=3, days=-1)
            if quarter_end > end_date:
                quarter_end = end_date
            
            self.create({
                'grant_id': grant_id,
                'name': _('Q%(quarter)d %(year)d Report') % {
                    'quarter': ((current_date.month - 1) // 3) + 1,
                    'year': current_date.year,
                },
                'report_type': 'quarterly',
                'report_period_start': current_date,
                'report_period_end': quarter_end,
                'report_date': quarter_end + relativedelta(days=30),
            })
            
            current_date = quarter_end + relativedelta(days=1)
            sequence += 1
        
        # Add final report
        self.create({
            'grant_id': grant_id,
            'name': _('Final Report'),
            'report_type': 'final',
            'report_period_start': grant.start_date,
            'report_period_end': grant.end_date,
            'report_date': grant.end_date + relativedelta(days=90),
        })
    
    @api.model
    def generate_due_reports(self):
        """Generate list of due reports for dashboard."""
        today = fields.Date.today()
        upcoming_date = today + relativedelta(days=30)
        
        due_reports = self.search([
            ('report_date', '<=', upcoming_date),
            ('report_date', '>=', today),
            ('state', 'in', ['draft', 'scheduled', 'in_preparation']),
        ])
        
        return due_reports
    
    @api.model
    def notify_upcoming_deadlines(self):
        """Notify users of upcoming reporting deadlines."""
        today = fields.Date.today()
        upcoming_date = today + relativedelta(days=7)
        
        # Find reports due in 7 days
        upcoming_reports = self.search([
            ('report_date', '<=', upcoming_date),
            ('report_date', '>=', today),
            ('state', 'in', ['draft', 'scheduled', 'in_preparation']),
            ('reminder_sent', '=', False),
        ])
        
        for report in upcoming_reports:
            report.action_send_reminder()
        
        # Find overdue reports
        overdue_reports = self.search([
            ('report_date', '<', today),
            ('state', 'in', ['draft', 'scheduled', 'in_preparation']),
        ])
        
        for report in overdue_reports:
            report.write({'state': 'overdue'})
            report.message_post(body=_('Report is overdue.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create reporting schedule with chatter message."""
        schedules = super(NgoGrantReportingSchedule, self).create(vals_list)
        for schedule in schedules:
            schedule.message_post(
                body=_('Reporting schedule %(name)s created') % {'name': schedule.name}
            )
        return schedules
