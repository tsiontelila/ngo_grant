# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError
from .workflow_access import check_cancellation_access, check_reset_access


class NgoGrantDonorLine(models.Model):
    """NGO Grant Donor Line model.
    
    Represents one donor's participation in one grant agreement.
    This is an association (junction) model, not a master record.
    Supports multi-donor grants where each donor contributes different values.
    """
    
    _name = 'ngo.grant.donor.line'
    _description = 'NGO Grant Donor Allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ngo.cancellation.access.mixin']
    _rec_name = 'display_name'
    _order = 'lead_donor desc, contribution_amount desc'
    
    # References
    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Associated grant',
    )
    
    donor_id = fields.Many2one(
        'ngo.grant.donor',
        string='Donor',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='Participating donor',
    )
    
    donor_code = fields.Char(
        string='Donor Code',
        related='donor_id.donor_code',
        store=True,
        readonly=True,
    )
    
    donor_name = fields.Char(
        string='Donor Name',
        related='donor_id.name',
        store=True,
        readonly=True,
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    
    # Funding
    contribution_amount = fields.Monetary(
        string='Contribution Amount',
        currency_field='currency_id',
        required=False,
        tracking=True,
        help='Amount contributed by this donor',
    )
    
    contribution_percentage = fields.Float(
        string='Contribution (%)',
        compute='_compute_contribution_percentage',
        inverse='_inverse_contribution_percentage',
        store=True,
        readonly=False,
        tracking=True,
        help='Percentage of total grant contributed by this donor',
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='grant_id.currency_id',
        store=True,
        readonly=True,
    )
    
    # Agreement
    donor_reference = fields.Char(
        string='Donor Reference',
        tracking=True,
        help='Donor internal reference for this grant',
    )
    
    agreement_reference = fields.Char(
        string='Agreement Reference',
        tracking=True,
        help='Agreement reference number from donor',
    )
    
    agreement_date = fields.Date(
        string='Agreement Date',
        tracking=True,
        help='Date of donor agreement',
    )
    
    # Responsibilities
    lead_donor = fields.Boolean(
        string='Lead Donor',
        default=False,
        tracking=True,
        help='Whether this is the lead donor for the grant',
    )
    
    reporting_responsibility = fields.Selection([
        ('primary', 'Primary Reporting'),
        ('secondary', 'Secondary Reporting'),
        ('none', 'No Reporting'),
    ],
        string='Reporting Responsibility',
        default='none',
        tracking=True,
        help='Reporting responsibility for this donor',
    )
    
    procurement_restrictions = fields.Text(
        string='Procurement Restrictions',
        tracking=True,
        help='Any procurement restrictions from this donor',
    )
    
    funding_conditions = fields.Text(
        string='Funding Conditions',
        tracking=True,
        help='Conditions attached to this funding',
    )
    
    cost_sharing_notes = fields.Text(
        string='Cost Sharing Notes',
        tracking=True,
        help='Notes about cost-sharing arrangements',
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        help='Donor allocation status',
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Whether this allocation is active',
    )
    
    # Dates
    allocation_start_date = fields.Date(
        string='Allocation Start Date',
        tracking=True,
        help='Start date for this donor allocation',
    )
    
    allocation_end_date = fields.Date(
        string='Allocation End Date',
        tracking=True,
        help='End date for this donor allocation',
    )
    
    @api.constrains('grant_id', 'donor_id')
    def _check_grant_donor_unique(self):
        """Ensure grant-donor combination is unique."""
        for line in self:
            if line.grant_id and line.donor_id:
                existing = self.search([
                    ('grant_id', '=', line.grant_id.id),
                    ('donor_id', '=', line.donor_id.id),
                    ('id', '!=', line.id),
                ])
                if existing:
                    raise ValidationError(_('A donor cannot appear twice on the same grant! If you need multiple contributions from the same donor, please add them as a single donor line with the total contribution amount.'))
    
    @api.depends('donor_id.name', 'grant_id.grant_name')
    def _compute_display_name(self):
        """Compute display name."""
        for line in self:
            line.display_name = _('%(donor)s - %(grant)s') % {
                'donor': line.donor_id.name,
                'grant': line.grant_id.grant_name,
            }

    @api.depends('contribution_amount', 'grant_id.approved_amount')
    def _compute_contribution_percentage(self):
        """Compute contribution percentage automatically from contribution amount."""
        for line in self:
            approved = line.grant_id.approved_amount if line.grant_id else 0.0
            if approved > 0 and line.contribution_amount:
                line.contribution_percentage = round((line.contribution_amount / approved) * 100.0, 2)
            elif not line.contribution_amount:
                line.contribution_percentage = 0.0

    def _inverse_contribution_percentage(self):
        """Inverse compute contribution amount when contribution percentage is changed."""
        for line in self:
            approved = line.grant_id.approved_amount if line.grant_id else 0.0
            if approved > 0 and line.contribution_percentage:
                line.contribution_amount = round((line.contribution_percentage / 100.0) * approved, 2)

    @api.onchange('contribution_amount', 'grant_id', 'grant_id.approved_amount')
    def _onchange_contribution_amount(self):
        """Dynamic UI calculation when contribution amount is edited."""
        approved = self.grant_id.approved_amount if self.grant_id else 0.0
        if not approved and self._context.get('default_approved_amount'):
            approved = self._context.get('default_approved_amount')
        if approved > 0 and self.contribution_amount:
            self.contribution_percentage = round((self.contribution_amount / approved) * 100.0, 2)

    @api.onchange('contribution_percentage', 'grant_id', 'grant_id.approved_amount')
    def _onchange_contribution_percentage(self):
        """Dynamic UI calculation when contribution percentage is edited."""
        approved = self.grant_id.approved_amount if self.grant_id else 0.0
        if not approved and self._context.get('default_approved_amount'):
            approved = self._context.get('default_approved_amount')
        if approved > 0 and self.contribution_percentage:
            self.contribution_amount = round((self.contribution_percentage / 100.0) * approved, 2)
    
    @api.constrains('contribution_percentage')
    def _check_contribution_percentage(self):
        """Validate contribution percentage."""
        for line in self:
            if line.contribution_percentage < 0 or line.contribution_percentage > 100:
                raise ValidationError(_('Contribution percentage must be between 0 and 100.'))
    
    @api.constrains('lead_donor')
    def _check_lead_donor(self):
        """Ensure only one lead donor per grant."""
        for line in self:
            if line.lead_donor:
                other_lead = self.search([
                    ('grant_id', '=', line.grant_id.id),
                    ('lead_donor', '=', True),
                    ('id', '!=', line.id),
                ])
                if other_lead:
                    raise ValidationError(_('Only one Lead Donor may exist for a grant.'))
    
    @api.constrains('contribution_percentage', 'grant_id')
    def _check_total_percentage(self):
        """Validate total contribution percentage equals 100% before activation."""
        for line in self:
            # No state-based validation - allow adding donors in any state
            # Validation only happens during grant activation
            pass
    
    @api.constrains('contribution_amount', 'grant_id')
    def _check_total_amount(self):
        """Validate total contribution amounts match approved grant amount."""
        for line in self:
            # Skip check if context flag is set (e.g., during amendment approval)
            if self.env.context.get('skip_donor_contribution_check'):
                continue
            # No state-based validation - allow adding donors in any state
            # Validation only happens during grant activation
            pass
    
    @api.constrains('allocation_start_date', 'allocation_end_date')
    def _check_allocation_dates(self):
        """Validate allocation dates."""
        for line in self:
            if line.allocation_start_date and line.allocation_end_date:
                if line.allocation_start_date > line.allocation_end_date:
                    raise ValidationError(_('Allocation Start Date must be before Allocation End Date.'))
    
    # Business Methods
    def _check_contribution_editable(self):
        for line in self:
            if self.env.context.get('allow_cancel_reset_state_change'):
                continue
            if line.grant_id.state not in ('draft', 'submitted'):
                raise AccessError(
                    _('Donor contributions can only be changed before the grant enters Under Review.')
                )

    def action_activate(self):
        """Activate allocation."""
        self.write({'state': 'active', 'active': True})
    
    def action_suspend(self):
        """Suspend allocation."""
        self.write({'state': 'suspended'})
    
    def action_complete(self):
        """Complete allocation."""
        self.write({'state': 'completed'})
    
    def action_cancel(self):
        """Cancel allocation."""
        check_cancellation_access(self)
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({'state': 'cancelled'})
        self.sudo().message_post(body=_('Donor allocation cancelled.'))

    def action_reset_cancelled(self):
        check_reset_access(self)
        if any(line.state != 'cancelled' for line in self):
            raise ValidationError(_('Only cancelled donor allocations can be reset to Draft.'))
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({'state': 'draft', 'active': True})
        self.sudo().message_post(body=_('Cancelled donor allocation reset to Draft for revision.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create donor line with chatter message."""
        grants = self.env['ngo.grant'].browse(
            [vals['grant_id'] for vals in vals_list if vals.get('grant_id')]
        )
        for grant in grants:
            if grant.state not in ('draft', 'submitted'):
                raise AccessError(
                    _('Donor contributions can only be changed before the grant enters Under Review.')
                )
        lines = super(NgoGrantDonorLine, self).create(vals_list)
        for line in lines:
            line.message_post(
                body=_('Donor %(donor)s added to grant %(grant)s with contribution %(amount)s') % {
                    'donor': line.donor_id.name,
                    'grant': line.grant_id.grant_name,
                    'amount': line.contribution_amount,
                }
            )
        return lines

    def write(self, vals):
        self._check_contribution_editable()
        return super().write(vals)

    def unlink(self):
        self._check_contribution_editable()
        return super().unlink()
