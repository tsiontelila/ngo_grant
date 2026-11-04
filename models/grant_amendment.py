# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class NgoGrantAmendment(models.Model):
    """NGO Grant Amendment model.
    
    Supports donor-approved changes such as budget revision, extension, additional funding, scope change, and activity revision.
    Each amendment creates a new approved version while preserving history.
    """
    
    _name = 'ngo.grant.amendment'
    _description = 'NGO Grant Amendment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'amendment_number'
    _order = 'amendment_date desc'
    
    # Identification
    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Associated grant',
    )

    amendment_number = fields.Char(
        string='Amendment Number',
        required=True,
        copy=False,
        tracking=True,
        help='Unique amendment reference',
    )
    
    amendment_version = fields.Integer(
        string='Amendment Version',
        required=True,
        default=1,
        tracking=True,
        help='Version number of this amendment',
    )
    
    previous_amendment_id = fields.Many2one(
        'ngo.grant.amendment',
        string='Previous Amendment',
        tracking=True,
        help='Previous amendment this one supersedes',
    )
    
    amendment_name = fields.Char(
        string='Amendment Name',
        required=True,
        tracking=True,
        help='Amendment title',
    )
    
    description = fields.Text(
        string='Description',
        required=True,
        help='Detailed description of the amendment',
    )
    
    amendment_reason = fields.Text(
        string='Amendment Reason',
        tracking=True,
        help='Reason for this amendment',
    )
    
    donor_reference = fields.Char(
        string='Donor Reference',
        tracking=True,
        help='Reference number from donor',
    )
    
    request_date = fields.Date(
        string='Request Date',
        tracking=True,
        help='Date when amendment was requested',
    )
    
    # Type
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
        tracking=True,
        help='Type of amendment',
    )
    
    # Financial Changes
    amount_change = fields.Monetary(
        string='Amount Change',
        currency_field='currency_id',
        tracking=True,
        help='Change in approved amount (positive for increase, negative for decrease)',
    )
    
    new_approved_amount = fields.Monetary(
        string='New Approved Amount',
        currency_field='currency_id',
        compute='_compute_new_approved_amount',
        store=True,
        help='New total approved amount after amendment',
    )
    
    previous_amount = fields.Monetary(
        string='Previous Amount',
        currency_field='currency_id',
        tracking=True,
        help='Grant approved amount before this amendment',
    )
    
    revised_amount = fields.Monetary(
        string='Revised Amount',
        currency_field='currency_id',
        tracking=True,
        help='Revised approved amount after amendment',
    )
    
    difference_amount = fields.Monetary(
        string='Difference Amount',
        currency_field='currency_id',
        compute='_compute_difference_amount',
        store=True,
        help='Difference between previous and revised amount',
    )
    
    previous_approved_amount = fields.Monetary(
        string='Previous Approved Amount',
        currency_field='currency_id',
        related='grant_id.approved_amount',
        readonly=True,
        store=True,
        help='Grant approved amount before this amendment',
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='grant_id.currency_id',
        store=True,
        readonly=True,
    )
    
    # Date Changes
    original_end_date = fields.Date(
        string='Original End Date',
        required=True,
        tracking=True,
        help='Original grant end date before amendment',
    )
    
    previous_end_date = fields.Date(
        string='Previous End Date',
        tracking=True,
        help='Previous grant end date before this amendment',
    )
    
    revised_end_date = fields.Date(
        string='Revised End Date',
        tracking=True,
        help='Revised grant end date after amendment',
    )
    
    new_end_date = fields.Date(
        string='New End Date',
        tracking=True,
        help='New grant end date after amendment',
    )
    
    extension_days = fields.Integer(
        string='Extension Days',
        compute='_compute_extension_days',
        store=True,
        help='Number of days extended',
    )
    
    amendment_date = fields.Date(
        string='Amendment Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date when amendment was approved',
    )
    
    effective_date = fields.Date(
        string='Effective Date',
        tracking=True,
        help='Date when amendment becomes effective',
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('superseded', 'Superseded'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        help='Amendment status',
    )
    
    # Approval
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        tracking=True,
        help='User who approved the amendment',
    )
    
    approval_date = fields.Date(
        string='Approval Date',
        tracking=True,
        help='Date when amendment was approved',
    )
    
    approval_reference = fields.Char(
        string='Approval Reference',
        tracking=True,
        help='Reference number for approval',
    )
    
    # Monitoring - Computed fields
    budget_version_count = fields.Integer(
        string='Budget Version Count',
        compute='_compute_budget_version_count',
        store=True,
        help='Number of budget versions affected',
    )
    
    document_count = fields.Integer(
        string='Document Count',
        compute='_compute_document_count',
        store=True,
        help='Number of documents linked to this amendment',
    )
    
    # Documents
    document_ids = fields.One2many(
        'ngo.grant.document',
        'amendment_id',
        string='Documents',
        help='Supporting documents for this amendment',
    )
    
    # Notes
    rejection_reason = fields.Text(
        string='Rejection Reason',
        help='Reason for rejection if amendment is rejected',
    )
    
    internal_notes = fields.Text(
        string='Internal Notes',
        help='Internal notes about this amendment',
    )

    @api.constrains('amendment_number')
    def _check_amendment_number_unique(self):
        """Ensure amendment number is unique."""
        for amendment in self:
            if amendment.amendment_number:
                existing = self.search([
                    ('amendment_number', '=', amendment.amendment_number),
                    ('id', '!=', amendment.id),
                ])
                if existing:
                    raise ValidationError(_('Amendment number must be unique!'))
    
    @api.depends('amount_change', 'grant_id.approved_amount')
    def _compute_new_approved_amount(self):
        """Compute new approved amount."""
        for amendment in self:
            amendment.new_approved_amount = amendment.grant_id.approved_amount + (amendment.amount_change or 0)
    
    @api.depends('original_end_date', 'new_end_date')
    def _compute_extension_days(self):
        """Compute extension days."""
        for amendment in self:
            if amendment.original_end_date and amendment.new_end_date:
                amendment.extension_days = (amendment.new_end_date - amendment.original_end_date).days
            else:
                amendment.extension_days = 0
    
    @api.depends('previous_amount', 'revised_amount')
    def _compute_difference_amount(self):
        """Compute difference amount."""
        for amendment in self:
            amendment.difference_amount = (amendment.revised_amount or 0) - (amendment.previous_amount or 0)
    
    def _compute_budget_version_count(self):
        """Compute budget version count (placeholder for future integration)."""
        for amendment in self:
            amendment.budget_version_count = 0
    
    @api.depends('document_ids')
    def _compute_document_count(self):
        """Compute document count."""
        for amendment in self:
            amendment.document_count = len(amendment.document_ids)
    
    @api.constrains('original_end_date', 'grant_id')
    def _check_original_end_date(self):
        """Validate original end date matches grant."""
        for amendment in self:
            if amendment.original_end_date != amendment.grant_id.end_date:
                raise ValidationError(_('Original End Date must match the current Grant End Date.'))
    
    @api.constrains('new_end_date')
    def _check_new_end_date(self):
        """Validate new end date."""
        for amendment in self:
            if amendment.new_end_date and amendment.new_end_date < amendment.original_end_date:
                raise ValidationError(_('New End Date cannot be before the Original End Date.'))
    
    # Workflow Methods
    def action_submit(self):
        """Submit for review."""
        self.write({'state': 'submitted'})
        self.message_post(body=_('Amendment submitted for review.'))
    
    def action_approve(self):
        """Approve amendment and update grant."""
        for amendment in self:
            amendment.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approval_date': fields.Date.today(),
            })
            
            # Update grant approved amount if there's a change
            if amendment.amount_change:
                amendment.grant_id.with_context(skip_donor_contribution_check=True).write({
                    'approved_amount': amendment.new_approved_amount,
                })
            
            # Update grant end date if changed
            if amendment.new_end_date:
                amendment.grant_id.with_context(skip_donor_contribution_check=True).write({
                    'end_date': amendment.new_end_date,
                })
            
            amendment.message_post(body=_('Amendment approved and grant updated.'))

    def action_reject(self):
        """Reject amendment."""
        self.write({'state': 'rejected'})
        self.message_post(body=_('Amendment rejected.'))
    
    def action_cancel(self):
        """Cancel amendment."""
        self.write({'state': 'cancelled'})
        self.message_post(body=_('Amendment cancelled.'))
    
    def action_restore(self):
        """Restore amendment to draft (manager only)."""
        for amendment in self:
            # Revert grant changes if amendment was previously approved
            if amendment.state in ('approved', 'active'):
                # Revert approved amount if it was changed
                if amendment.amount_change:
                    amendment.grant_id.with_context(skip_donor_contribution_check=True).write({
                        'approved_amount': amendment.grant_id.approved_amount - amendment.amount_change,
                    })
                # Revert end date if it was changed
                if amendment.new_end_date:
                    amendment.grant_id.with_context(skip_donor_contribution_check=True).write({
                        'end_date': amendment.original_end_date,
                    })
        
        self.with_context(skip_amendment_write_check=True).write({
            'state': 'draft',
            'approved_by': False,
            'approval_date': False
        })
        self.message_post(body=_('Amendment restored to draft. Grant changes reverted.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create amendment with auto-generated number."""
        for vals in vals_list:
            if not vals.get('amendment_number'):
                vals['amendment_number'] = self.env['ir.sequence'].next_by_code('ngo.grant.amendment') or 'AMD-NEW'
            if not vals.get('original_end_date'):
                grant_id = vals.get('grant_id')
                if grant_id:
                    grant = self.env['ngo.grant'].browse(grant_id)
                    vals['original_end_date'] = grant.end_date
        amendments = super(NgoGrantAmendment, self).create(vals_list)
        for amendment in amendments:
            amendment.message_post(
                body=_('Amendment %s created for grant %s') % (
                    amendment.amendment_number,
                    amendment.grant_id.grant_number
                )
            )
        return amendments
    
    def write(self, vals):
        """Prevent modification after approval."""
        for amendment in self:
            # Skip check if context flag is set (e.g., during restore)
            if self.env.context.get('skip_amendment_write_check'):
                continue
            if amendment.state == 'approved' and vals.keys() != {'state'}:
                raise ValidationError(_('Approved amendments cannot be modified.'))
        return super(NgoGrantAmendment, self).write(vals)
    
    def unlink(self):
        """Prevent deletion beyond Draft."""
        for amendment in self:
            if amendment.state != 'draft':
                raise ValidationError(_('Only draft amendments can be deleted.'))
        return super(NgoGrantAmendment, self).unlink()
