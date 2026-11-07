# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError
from .workflow_access import check_cancellation_access, check_reset_access


class NgoGrantCompliance(models.Model):
    """NGO Grant Compliance model.
    
    Tracks grant-specific compliance obligations such as audit due, financial report due, narrative report due, asset register due, procurement review, and environmental compliance.
    """
    
    _name = 'ngo.grant.compliance'
    _description = 'NGO Grant Compliance'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ngo.cancellation.access.mixin']
    _order = 'due_date, priority desc'

    def init(self):
        """Move legacy subgrant compliance items out of their parent grant."""
        self.env.cr.execute(
            f'UPDATE "{self._table}" SET grant_id = NULL WHERE subgrant_id IS NOT NULL AND grant_id IS NOT NULL'
        )
    
    # References
    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=False,
        ondelete='cascade',
        tracking=True,
        help='Associated grant',
    )
    subgrant_id = fields.Many2one('ngo.subgrant', string='Subgrant', ondelete='cascade', tracking=True)
    
    # Identification
    name = fields.Char(
        string='Requirement',
        required=True,
        tracking=True,
        help='Compliance requirement name',
    )
    
    compliance_type = fields.Selection([
        ('audit', 'Audit'),
        ('financial_report', 'Financial Report'),
        ('narrative_report', 'Narrative Report'),
        ('asset_register', 'Asset Register'),
        ('procurement_review', 'Procurement Review'),
        ('environmental', 'Environmental Compliance'),
        ('safety', 'Safety Compliance'),
        ('legal', 'Legal Compliance'),
        ('donor_specific', 'Donor-Specific Requirement'),
        ('other', 'Other'),
    ],
        string='Compliance Type',
        required=True,
        tracking=True,
        help='Type of compliance requirement',
    )
    
    # Dates
    due_date = fields.Date(
        string='Due Date',
        required=True,
        tracking=True,
        help='Date when compliance is due',
    )
    
    completed_date = fields.Date(
        string='Completed Date',
        tracking=True,
        help='Date when compliance was completed',
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('evidence_submitted', 'Evidence Submitted'),
        ('under_verification', 'Under Verification'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('waived', 'Waived'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        help='Compliance status',
    )
    
    # Priority
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ],
        string='Priority',
        default='medium',
        tracking=True,
        help='Compliance priority',
    )
    
    # Responsibility
    responsible_employee_id = fields.Many2one(
        'hr.employee',
        string='Responsible Employee',
        tracking=True,
        help='Employee responsible for this compliance item',
    )
    
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsible User',
        tracking=True,
        help='User responsible for this compliance item',
    )
    
    document_id = fields.Many2one(
        'ngo.grant.document',
        string='Evidence Document',
        tracking=True,
        help='Document linked to this compliance item',
    )
    
    # Details
    description = fields.Text(
        string='Description',
        tracking=True,
        help='Detailed description of the requirement',
    )
    
    requirements = fields.Text(
        string='Requirements',
        tracking=True,
        help='Specific requirements to meet compliance',
    )
    
    # Evidence
    document_ids = fields.One2many(
        'ngo.grant.document',
        'compliance_id',
        string='Evidence Documents',
        help='Documents supporting compliance',
    )
    subgrant_evidence_document_ids = fields.One2many(
        'ngo.grant.document', 'compliance_id',
        string='Subgrant Evidence Documents',
        domain=[('subgrant_id', '!=', False)],
    )
    subgrant_legacy_document_ids = fields.One2many(
        'ngo.subgrant.document', 'compliance_id',
        string='Existing Subgrant Evidence Documents',
    )
    
    notes = fields.Text(
        string='Notes',
        tracking=True,
        help='Additional notes',
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
        help='Whether compliance item is overdue',
    )
    
    days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_days_overdue',
        store=True,
        help='Days compliance item is overdue',
    )
    
    days_until_due = fields.Integer(
        string='Days Until Due',
        compute='_compute_days_until_due',
        store=True,
        help='Days until compliance item is due',
    )
    
    # Verification
    verified = fields.Boolean(
        string='Verified',
        default=False,
        tracking=True,
        help='Whether compliance has been verified',
    )
    
    verified_by = fields.Many2one(
        'res.users',
        string='Verified By',
        tracking=True,
        help='User who verified compliance',
    )
    
    verified_date = fields.Date(
        string='Verified Date',
        tracking=True,
        help='Date when compliance was verified',
    )
    
    verification_notes = fields.Text(
        string='Verification Notes',
        tracking=True,
        help='Notes from verification',
    )
    
    @api.onchange('grant_id')
    def _onchange_grant_id(self):
        if self.grant_id:
            self.subgrant_id = False

    @api.onchange('subgrant_id')
    def _onchange_subgrant_id(self):
        if self.subgrant_id:
            self.grant_id = False

    @api.constrains('grant_id', 'subgrant_id')
    def _check_single_owner(self):
        for compliance in self:
            if bool(compliance.grant_id) == bool(compliance.subgrant_id):
                raise ValidationError(_('Select either a Grant or a Subgrant for compliance, not both.'))

    @api.constrains('grant_id', 'subgrant_id', 'name')
    def _check_name_unique_per_owner(self):
        """Ensure compliance name is unique within its grant or subgrant."""
        for compliance in self:
            if compliance.name and compliance.grant_id:
                existing = self.search([
                    ('grant_id', '=', compliance.grant_id.id),
                    ('name', '=', compliance.name),
                    ('id', '!=', compliance.id),
                ])
            elif compliance.name and compliance.subgrant_id:
                existing = self.search([
                    ('subgrant_id', '=', compliance.subgrant_id.id),
                    ('name', '=', compliance.name),
                    ('id', '!=', compliance.id),
                ])
            else:
                existing = self.browse()
            if existing:
                raise ValidationError(_('Compliance requirement name must be unique within its grant or subgrant.'))
    
    @api.depends('due_date', 'completed_date')
    def _compute_is_overdue(self):
        """Compute whether compliance item is overdue."""
        for compliance in self:
            if compliance.due_date and not compliance.completed_date:
                compliance.is_overdue = compliance.due_date < fields.Date.today()
            else:
                compliance.is_overdue = False
    
    @api.depends('due_date', 'completed_date')
    def _compute_days_overdue(self):
        """Compute days overdue."""
        for compliance in self:
            if compliance.due_date and not compliance.completed_date and compliance.due_date < fields.Date.today():
                compliance.days_overdue = (fields.Date.today() - compliance.due_date).days
            else:
                compliance.days_overdue = 0
    
    @api.depends('due_date', 'completed_date')
    def _compute_days_until_due(self):
        """Compute days until due."""
        for compliance in self:
            if compliance.due_date and not compliance.completed_date and compliance.due_date >= fields.Date.today():
                compliance.days_until_due = (compliance.due_date - fields.Date.today()).days
            else:
                compliance.days_until_due = 0
    
    @api.constrains('completed_date', 'due_date')
    def _check_completed_date(self):
        """Validate completed date."""
        for compliance in self:
            if compliance.completed_date and compliance.due_date:
                if compliance.completed_date > compliance.due_date:
                    # Allow but flag as late
                    pass
    
    # Business Methods
    def write(self, vals):
        locked_states = ('completed', 'cancelled')
        if not self.env.su and 'state' in vals and vals['state'] != 'cancelled' and any(record.state in locked_states for record in self):
            raise AccessError(_('Approved compliance cannot be changed until an administrator cancels it.'))
        if not self.env.su and set(vals) - {'state', 'reminder_sent', 'reminder_count'}:
            if any(record.state in locked_states for record in self):
                raise AccessError(_('Approved compliance details are locked. An administrator must cancel the item before it can be reset and edited.'))
        return super().write(vals)

    def action_start(self):
        """Mark as in progress."""
        self.write({'state': 'in_progress'})
        self.message_post(body=_('Compliance marked as in progress.'))
    
    def action_submit(self):
        """Submit for approval."""
        self.write({
            'state': 'evidence_submitted',
            'completed_date': fields.Date.today(),
        })
        self.message_post(body=_('Compliance submitted for approval.'))
    
    def action_approve(self):
        """Approve compliance."""
        self.write({'state': 'completed'})
        self.message_post(body=_('Compliance approved.'))
    
    def action_reject(self):
        """Reject compliance."""
        self.write({'state': 'rejected'})
        self.message_post(body=_('Compliance rejected.'))

    def action_cancel(self):
        check_cancellation_access(self)
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({'state': 'cancelled'})
        self.sudo().message_post(body=_('Compliance cancelled.'))

    def action_reset_cancelled(self):
        check_reset_access(self)
        for record in self:
            if record.state != 'cancelled':
                raise ValidationError(_('Only cancelled compliance items can be reset to Draft.'))
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({
            'state': 'draft', 'completed_date': False, 'verified': False,
            'verified_by': False, 'verified_date': False,
        })
        self.sudo().message_post(body=_('Cancelled compliance item reset to Draft for revision.'))
    
    def action_waive(self):
        """Waive compliance."""
        self.write({'state': 'waived'})
        self.message_post(body=_('Compliance waived.'))
    
    def action_send_reminder(self):
        """Send reminder notification."""
        for compliance in self:
            compliance.write({
                'reminder_sent': True,
                'reminder_count': compliance.reminder_count + 1,
            })
            compliance.message_post(
                body=_('Reminder sent to %(user)s') % {'user': compliance.responsible_id.name if compliance.responsible_id else 'Responsible User'}
            )
            # Send email notification if responsible user is set
            if compliance.responsible_id:
                template = self.env.ref('ngo_grant.email_template_compliance_reminder', raise_if_not_found=False)
                if template:
                    # Older installed databases may still contain the legacy
                    # template expression in ``lang``. Repair it before send.
                    if template.lang != 'en_US':
                        template.sudo().write({'lang': 'en_US'})
                    template.send_mail(compliance.id, force_send=True)
    
    @api.model
    def check_due_items(self):
        """Check for overdue compliance items and send reminders."""
        today = fields.Date.today()
        upcoming_date = today + relativedelta(days=7)
        
        # Find items due in 7 days
        upcoming_items = self.search([
            ('due_date', '<=', upcoming_date),
            ('due_date', '>=', today),
            ('state', 'in', ['draft', 'assigned', 'in_progress']),
            ('reminder_sent', '=', False),
        ])
        
        for item in upcoming_items:
            item.action_send_reminder()
        
        # Find overdue items
        overdue_items = self.search([
            ('due_date', '<', today),
            ('state', 'in', ['draft', 'assigned', 'in_progress']),
        ])
        
        for item in overdue_items:
            item.write({'state': 'overdue'})
            item.message_post(body=_('Compliance item is overdue.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create compliance with chatter message."""
        compliances = super(NgoGrantCompliance, self).create(vals_list)
        for compliance in compliances:
            compliance.message_post(
                body=_('Compliance requirement %(name)s created') % {'name': compliance.name}
            )
        return compliances
