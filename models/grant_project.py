# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class NgoGrantProject(models.Model):
    """NGO Grant Project model.
    
    Association (junction) model for Grant-Project relationship.
    One project may receive funding from multiple grants.
    One grant may fund multiple projects.
    """
    
    _name = 'ngo.grant.project'
    _description = 'NGO Grant Project Allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'sequence, id'
    
    # References
    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Associated grant',
    )
    
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Funded project',
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    
    # Funding
    allocation_amount = fields.Monetary(
        string='Allocation Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
        help='Amount allocated to this project',
    )
    
    allocation_percentage = fields.Float(
        string='Allocation (%)',
        compute='_compute_allocation_percentage',
        store=True,
        digits=(16, 4),
        tracking=True,
        help='Percentage of grant allocated to this project',
    )

    is_active = fields.Boolean(
        string='Active',
        compute='_compute_is_active',
        help='Whether this allocation is active',
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='grant_id.currency_id',
        store=True,
        readonly=True,
    )
    
    # Dates
    funding_start_date = fields.Date(
        string='Funding Start Date',
        tracking=True,
        help='Start date for this funding allocation',
    )
    
    funding_end_date = fields.Date(
        string='Funding End Date',
        tracking=True,
        help='End date for this funding allocation',
    )
    
    # Classification
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ],
        string='Priority',
        default='medium',
        tracking=True,
        help='Funding priority',
    )
    
    funding_role = fields.Selection([
        ('primary', 'Primary'),
        ('supplementary', 'Supplementary'),
        ('matching', 'Matching'),
        ('co_funding', 'Co-Funding'),
    ],
        string='Funding Role',
        tracking=True,
        help='Role of this funding source',
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        tracking=True,
        help='Sequence for ordering',
    )
    
    # Status
    is_primary_funding = fields.Boolean(
        string='Primary Funding',
        default=False,
        tracking=True,
        help='Whether this is the primary funding source for the project',
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Whether this allocation is active',
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        help='Allocation status',
    )
    
    # Monitoring - Computed fields
    utilized_amount = fields.Monetary(
        string='Utilized Amount',
        currency_field='currency_id',
        compute='_compute_utilized_amount',
        store=True,
        help='Amount utilized from this allocation',
    )
    
    remaining_amount = fields.Monetary(
        string='Remaining Amount',
        currency_field='currency_id',
        compute='_compute_remaining_amount',
        store=True,
        help='Remaining amount in this allocation',
    )
    
    budget_count = fields.Integer(
        string='Budget Count',
        compute='_compute_budget_count',
        store=True,
        help='Number of budgets linked to this allocation',
    )
    
    procurement_count = fields.Integer(
        string='Procurement Count',
        compute='_compute_procurement_count',
        store=True,
        help='Number of procurements linked to this allocation',
    )
    
    cash_request_count = fields.Integer(
        string='Cash Request Count',
        compute='_compute_cash_request_count',
        store=True,
        help='Number of cash requests linked to this allocation',
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this allocation',
    )
    
    @api.depends('grant_id.grant_name', 'project_id.name')
    def _compute_display_name(self):
        """Compute display name."""
        for allocation in self:
            allocation.display_name = _('%(grant)s - %(project)s') % {
                'grant': allocation.grant_id.grant_name,
                'project': allocation.project_id.name,
            }

    @api.depends('allocation_amount', 'grant_id.approved_amount')
    def _compute_allocation_percentage(self):
        for allocation in self:
            approved_amount = allocation.grant_id.approved_amount
            allocation.allocation_percentage = (
                allocation.allocation_amount / approved_amount
                if approved_amount > 0 else 0.0
            )

    @api.depends('state')
    def _compute_is_active(self):
        for allocation in self:
            allocation.is_active = allocation.state == 'active'
    
    @api.constrains('allocation_percentage')
    def _check_allocation_percentage(self):
        """Validate allocation percentage."""
        for allocation in self:
            if allocation.allocation_percentage < 0 or allocation.allocation_percentage > 1:
                raise ValidationError(_('Allocation percentage must be between 0% and 100%.'))
    
    @api.constrains('funding_start_date', 'funding_end_date')
    def _check_funding_dates(self):
        """Validate funding dates."""
        for allocation in self:
            if allocation.funding_start_date and allocation.funding_end_date:
                if allocation.funding_start_date > allocation.funding_end_date:
                    raise ValidationError(_('Funding Start Date must be before Funding End Date.'))
    
    @api.constrains('is_primary_funding')
    def _check_primary_funding(self):
        """Ensure only one primary funding per project."""
        for allocation in self:
            if allocation.is_primary_funding:
                other_primary = self.search([
                    ('project_id', '=', allocation.project_id.id),
                    ('is_primary_funding', '=', True),
                    ('id', '!=', allocation.id),
                ])
                if other_primary:
                    raise ValidationError(_('Only one primary funding source is allowed per project.'))
    
    @api.constrains('allocation_amount', 'grant_id')
    def _check_allocation_amount(self):
        """Validate total allocations don't exceed grant amount."""
        for allocation in self:
            grant = allocation.grant_id
            total_allocated = sum(grant.project_ids.mapped('allocation_amount'))
            if grant.currency_id.compare_amounts(total_allocated, grant.approved_amount) > 0:
                raise ValidationError(_('Total allocations cannot exceed the approved grant amount.'))
    
    # Business Methods
    def action_activate(self):
        """Activate allocation."""
        self.write({'state': 'active'})
        self.message_post(body=_('Allocation activated.'))
    
    def action_suspend(self):
        """Suspend allocation."""
        self.write({'state': 'suspended'})
        self.message_post(body=_('Allocation suspended.'))
    
    def action_complete(self):
        """Complete allocation."""
        self.write({'state': 'completed'})
        self.message_post(body=_('Allocation completed.'))
    
    def action_cancel(self):
        """Cancel allocation."""
        self.write({'state': 'cancelled'})
        self.message_post(body=_('Allocation cancelled.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create allocation with chatter message."""
        allocations = super(NgoGrantProject, self).create(vals_list)
        for allocation in allocations:
            allocation.message_post(
                body=_('Allocation created: %(amount)s to %(project)s') % {
                    'amount': allocation.allocation_amount,
                    'project': allocation.project_id.name,
                }
            )
        return allocations
    
    @api.depends('allocation_amount')
    def _compute_utilized_amount(self):
        """Compute utilized amount (placeholder for future integration)."""
        for allocation in self:
            allocation.utilized_amount = 0.0
    
    @api.depends('allocation_amount', 'utilized_amount')
    def _compute_remaining_amount(self):
        """Compute remaining amount."""
        for allocation in self:
            allocation.remaining_amount = allocation.allocation_amount - allocation.utilized_amount
    
    def _compute_budget_count(self):
        """Compute budget count (placeholder for future integration)."""
        for allocation in self:
            allocation.budget_count = 0
    
    def _compute_procurement_count(self):
        """Compute procurement count (placeholder for future integration)."""
        for allocation in self:
            allocation.procurement_count = 0
    
    def _compute_cash_request_count(self):
        """Compute cash request count (placeholder for future integration)."""
        for allocation in self:
            allocation.cash_request_count = 0
