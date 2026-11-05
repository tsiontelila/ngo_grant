# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError


class NgoGrant(models.Model):
    """NGO Grant model.
    
    The master governance record for donor funding.
    A Grant represents the legally approved funding agreement between the NGO and a donor.
    """
    
    _name = 'ngo.grant'
    _description = 'NGO Grant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'grant_name'
    _order = 'grant_number desc'
    
    # Identification
    grant_number = fields.Char(
        string='Grant Number',
        required=True,
        copy=False,
        tracking=True,
        help='Unique grant reference entered manually',
    )
    
    grant_name = fields.Char(
        string='Grant Name',
        required=True,
        tracking=True,
        help='Official grant title',
    )
    
    short_name = fields.Char(
        string='Short Name',
        tracking=True,
        help='Internal abbreviation',
    )
    
    description = fields.Text(
        string='Description',
        help='Grant description',
    )
    
    # Donor - Multi-donor support through donor_line_ids
    donor_line_ids = fields.One2many(
        'ngo.grant.donor.line',
        'grant_id',
        string='Donor Allocations',
        tracking=True,
        help='Participating donors and their contributions',
    )
    
    # Disbursements
    disbursement_ids = fields.One2many(
        'ngo.grant.disbursement',
        'grant_id',
        string='Disbursements',
        tracking=True,
        help='Grant disbursement transactions',
    )

    subgrant_ids = fields.One2many('ngo.subgrant', 'grant_id', string='Subgrants')
    subgrant_amount = fields.Monetary(string='Subgrant Amount', currency_field='currency_id', compute='_compute_subgrant_amount', store=True)
    subgrant_count = fields.Integer(string='Subgrant Count', compute='_compute_subgrant_count')

    @api.depends('subgrant_ids')
    def _compute_subgrant_count(self):
        for grant in self:
            grant.subgrant_count = len(grant.subgrant_ids)

    @api.depends('subgrant_ids.approved_amount')
    def _compute_subgrant_amount(self):
        for grant in self:
            grant.subgrant_amount = sum(grant.subgrant_ids.mapped('approved_amount'))
    
    # Computed donor reference for display
    donor_reference = fields.Char(
        string='Donor Reference',
        compute='_compute_donor_reference',
        store=True,
        help='Combined donor reference',
    )
    
    # Funding
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
        help='Grant currency',
    )
    
    approved_amount = fields.Monetary(
        string='Approved Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
        help='Total approved grant amount',
    )
    
    disbursed_amount = fields.Monetary(
        string='Disbursed Amount',
        currency_field='currency_id',
        compute='_compute_disbursed_amount',
        store=True,
        help='Total amount disbursed',
    )
    
    total_contributed_amount = fields.Monetary(
        string='Total Contributed Amount',
        currency_field='currency_id',
        compute='_compute_total_contributed_amount',
        store=True,
        help='Sum of all donor contributions',
    )
    
    remaining_contribution_amount = fields.Monetary(
        string='Remaining Contribution Amount',
        currency_field='currency_id',
        compute='_compute_remaining_contribution_amount',
        store=True,
        help='Amount still to be contributed by donors',
    )
    
    remaining_amount = fields.Monetary(
        string='Remaining Amount',
        currency_field='currency_id',
        compute='_compute_remaining_amount',
        store=False,
        help='Remaining available amount',
    )
    
    # Dates
    agreement_date = fields.Date(
        string='Agreement Date',
        tracking=True,
        help='Date when grant agreement was signed',
    )
    
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        help='Grant start date',
    )
    
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        help='Grant end date',
    )
    
    close_date = fields.Date(
        string='Close Date',
        tracking=True,
        help='Actual grant closure date',
    )
    
    # Classification
    funding_type_id = fields.Many2one(
        'ngo.funding.type',
        string='Funding Type',
        tracking=True,
        help='Funding classification',
    )

    program_area_id = fields.Many2one(
        'ngo.program.area',
        string='Program Area',
        tracking=True,
        help='Program area supported by this grant',
    )

    sector_id = fields.Many2one(
        'ngo.sector',
        string='Sector',
        tracking=True,
        help='Sector supported by this grant',
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
    ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        help='Grant status',
    )
    
    grant_stage = fields.Selection(
        related='state',
        string='Grant Stage',
        readonly=True,
        store=True,
        help='Current lifecycle stage, synchronized with the grant status',
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether the grant is active',
    )

    # Organization
    company_id = fields.Many2one(
        'res.company',
        string='Organization',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        help='Operating organization',
    )
    
    # Smart-button counts are defined below alongside One2many fields
    
    # Restriction Type
    restriction_type = fields.Selection([
        ('restricted', 'Restricted'),
        ('unrestricted', 'Unrestricted'),
    ], string='Grant Restriction Type', default='restricted', required=True, tracking=True, help='Restricted or Unrestricted grant funding')

    # Multi-year Fiscal Sub-budgets
    budget_period_ids = fields.One2many(
        'ngo.grant.budget.period',
        'grant_id',
        string='Fiscal Sub-Budgets',
    )

    # Milestones & Release Conditions
    milestone_ids = fields.One2many(
        'ngo.grant.milestone',
        'grant_id',
        string='Milestones & Release Conditions',
    )

    # Multi-level Approval Steps
    approval_step_ids = fields.One2many(
        'ngo.grant.approval.step',
        'grant_id',
        string='Approval Chain',
    )

    audit_log_ids = fields.One2many(
        'ngo.grant.audit.log',
        'grant_id',
        string='Audit Trail Logs',
        readonly=True,
    )

    # Child models
    project_ids = fields.One2many(
        'ngo.grant.project',
        'grant_id',
        string='Projects',
        help='Funded projects',
    )
    
    amendment_ids = fields.One2many(
        'ngo.grant.amendment',
        'grant_id',
        string='Amendments',
        help='Grant amendments',
    )
    
    document_ids = fields.One2many(
        'ngo.grant.document',
        'grant_id',
        string='Documents',
        help='Grant documents',
    )
    
    compliance_ids = fields.One2many(
        'ngo.grant.compliance',
        'grant_id',
        string='Compliance Items',
        help='Compliance requirements',
    )
    
    reporting_schedule_ids = fields.One2many(
        'ngo.grant.reporting.schedule',
        'grant_id',
        string='Reporting Schedules',
        help='Reporting schedules',
    )
    
    # Smart button counts
    project_count = fields.Integer(
        string='Project Count',
        compute='_compute_project_count',
        store=False,
    )
    
    amendment_count = fields.Integer(
        string='Amendment Count',
        compute='_compute_amendment_count',
        store=False,
    )
    
    compliance_count = fields.Integer(
        string='Compliance Count',
        compute='_compute_compliance_count',
        store=False,
    )
    
    reporting_schedule_count = fields.Integer(
        string='Reporting Schedule Count',
        compute='_compute_reporting_schedule_count',
        store=False,
    )
    
    disbursement_count = fields.Integer(
        string='Disbursement Count',
        compute='_compute_disbursement_count',
        store=False,
    )
    
    @api.constrains('grant_number')
    def _check_grant_number_unique(self):
        """Ensure grant number is unique."""
        for grant in self:
            if grant.grant_number:
                existing = self.search([
                    ('grant_number', '=', grant.grant_number),
                    ('id', '!=', grant.id),
                ])
                if existing:
                    raise ValidationError(_('Grant number must be unique!'))

    @api.constrains('sector_id', 'program_area_id')
    def _check_program_area_sector(self):
        for grant in self:
            if (
                grant.sector_id
                and grant.program_area_id
                and grant.program_area_id.sector_id != grant.sector_id
            ):
                raise ValidationError(
                    _('The selected Program Area must belong to the selected Sector.')
                )

    @api.onchange('sector_id')
    def _onchange_sector_id(self):
        for grant in self:
            if grant.program_area_id and grant.program_area_id.sector_id != grant.sector_id:
                grant.program_area_id = False
    
    @api.depends('donor_line_ids')
    def _compute_donor_reference(self):
        """Compute combined donor reference."""
        for grant in self:
            if grant.donor_line_ids:
                donors = grant.donor_line_ids.mapped('donor_id').mapped('donor_code')
                grant.donor_reference = ', '.join(donors)
            else:
                grant.donor_reference = ''
    
    @api.depends('project_ids')
    def _compute_project_count(self):
        """Compute project count."""
        for grant in self:
            grant.project_count = len(grant.project_ids)
    
    @api.depends('amendment_ids')
    def _compute_amendment_count(self):
        """Compute amendment count."""
        for grant in self:
            grant.amendment_count = len(grant.amendment_ids)
    
    @api.depends('compliance_ids')
    def _compute_compliance_count(self):
        """Compute compliance count."""
        for grant in self:
            grant.compliance_count = len(grant.compliance_ids)
    
    @api.depends('reporting_schedule_ids')
    def _compute_reporting_schedule_count(self):
        """Compute reporting schedule count."""
        for grant in self:
            grant.reporting_schedule_count = len(grant.reporting_schedule_ids)
    
    @api.depends('disbursement_ids')
    def _compute_disbursement_count(self):
        """Compute disbursement count."""
        for grant in self:
            grant.disbursement_count = len(grant.disbursement_ids)
    
    @api.depends('disbursement_ids.amount', 'disbursement_ids.state')
    def _compute_disbursed_amount(self):
        """Compute disbursed amount from processed disbursements."""
        for grant in self:
            grant.disbursed_amount = sum(
                disbursement.amount for disbursement in grant.disbursement_ids
                if disbursement.state == 'processed'
            )
    
    def _compute_remaining_amount(self):
        """Compute remaining amount."""
        for grant in self:
            grant.remaining_amount = grant.approved_amount - grant.disbursed_amount
    
    @api.depends('donor_line_ids.contribution_amount')
    def _compute_total_contributed_amount(self):
        """Compute total contributed amount from all donors."""
        for grant in self:
            grant.total_contributed_amount = sum(
                donor_line.contribution_amount for donor_line in grant.donor_line_ids
            )
    
    @api.depends('approved_amount', 'total_contributed_amount')
    def _compute_remaining_contribution_amount(self):
        """Compute remaining contribution amount."""
        for grant in self:
            grant.remaining_contribution_amount = grant.approved_amount - grant.total_contributed_amount

    @api.onchange('approved_amount')
    def _onchange_approved_amount_donor_lines(self):
        """Update donor line contribution percentages when approved amount changes."""
        if self.approved_amount > 0 and self.donor_line_ids:
            for line in self.donor_line_ids:
                if line.contribution_amount:
                    line.contribution_percentage = round((line.contribution_amount / self.approved_amount) * 100.0, 2)
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Validate dates."""
        for grant in self:
            if grant.start_date and grant.end_date:
                if grant.start_date > grant.end_date:
                    raise ValidationError(_('Start Date must be before End Date.'))
            if grant.agreement_date and grant.start_date:
                if grant.agreement_date > grant.start_date:
                    raise ValidationError(_('Agreement Date must be before Start Date.'))
    
    @api.constrains('approved_amount')
    def _check_approved_amount(self):
        """Validate approved amount."""
        for grant in self:
            if grant.approved_amount <= 0:
                raise ValidationError(_('Approved Amount must be greater than zero.'))
    
    @api.constrains('donor_line_ids', 'approved_amount')
    def _check_donor_contributions(self):
        """Validate donor contributions match approved amount."""
        for grant in self:
            # Skip check if context flag is set (e.g., during amendment restore)
            if self.env.context.get('skip_donor_contribution_check'):
                continue
            # No state-based validation - allow adding donors in any state
            # Validation only happens during grant activation
    
    # Workflow Methods
    def action_submit(self):
        """Submit for review."""
        self._check_manager_access()
        self.with_context(allow_workflow_state_change=True).write({'state': 'submitted'})
        self.message_post(body=_('Grant submitted for review.'))
    
    def action_send_for_review(self):
        """Send for under review."""
        self._check_manager_access()
        self.with_context(allow_workflow_state_change=True).write({'state': 'under_review'})
        self.message_post(body=_('Grant sent for under review.'))
    
    def action_approve(self):
        """Approve grant."""
        self._check_manager_access()
        self.with_context(allow_workflow_state_change=True).write({'state': 'approved'})
        self.message_post(body=_('Grant approved.'))
    
    def action_activate(self):
        """Activate grant."""
        self._check_manager_access()
        for grant in self:
            # Validate donor contributions match approved amount before activation
            if grant.donor_line_ids:
                total_contribution = sum(grant.donor_line_ids.mapped('contribution_amount'))
                if abs(total_contribution - grant.approved_amount) > 0.01:
                    raise ValidationError(_('Total donor contributions must equal the approved amount before activation.'))
        self.with_context(allow_workflow_state_change=True).write({'state': 'active', 'active': True})
        self.message_post(body=_('Grant activated.'))
    
    def action_suspend(self):
        """Suspend grant."""
        self._check_manager_access()
        self.with_context(allow_workflow_state_change=True).write({'state': 'suspended'})
        self.message_post(body=_('Grant suspended.'))
    
    def action_close(self):
        """Close grant."""
        self._check_manager_access()
        self.with_context(allow_workflow_state_change=True).write({
            'state': 'closed',
            'close_date': fields.Date.today(),
            'active': False,
        })
        self.message_post(body=_('Grant closed.'))
    
    def action_cancel(self):
        """Cancel grant."""
        self._check_manager_access()
        self.with_context(allow_workflow_state_change=True).write({'state': 'cancelled', 'active': False})
        self.message_post(body=_('Grant cancelled.'))
    
    def _check_manager_access(self):
        if not self.env.is_admin() and not self.env.user.has_group('ngo_grant.group_ngo_manager'):
            raise AccessError(_('Only NGO Grant Managers can perform this action.'))

    def action_view_projects(self):
        """View projects for this grant."""
        self.ensure_one()
        action = self.env.ref('ngo_grant.action_grant_project').read()[0]
        action['domain'] = [('grant_id', '=', self.id)]
        action['context'] = {'default_grant_id': self.id}
        return action

    def action_view_subgrants(self):
        self.ensure_one()
        action = self.env.ref('ngo_grant.action_subgrant').read()[0]
        action['domain'] = [('grant_id', '=', self.id)]
        action['context'] = {'default_grant_id': self.id}
        return action
    
    def action_view_amendments(self):
        """View amendments for this grant."""
        self.ensure_one()
        action = self.env.ref('ngo_grant.action_amendment').read()[0]
        action['domain'] = [('grant_id', '=', self.id)]
        action['context'] = {'default_grant_id': self.id}
        return action
    
    def action_view_compliance(self):
        """View compliance items for this grant."""
        self.ensure_one()
        action = self.env.ref('ngo_grant.action_compliance').read()[0]
        action['domain'] = [('grant_id', '=', self.id)]
        action['context'] = {'default_grant_id': self.id}
        return action
    
    def action_view_reports(self):
        """View reporting schedules for this grant."""
        self.ensure_one()
        action = self.env.ref('ngo_grant.action_reporting_schedule').read()[0]
        action['domain'] = [('grant_id', '=', self.id)]
        action['context'] = {'default_grant_id': self.id}
        return action
    
    def action_view_disbursements(self):
        """View disbursements for this grant."""
        self.ensure_one()
        action = self.env.ref('ngo_grant.action_disbursement').read()[0]
        action['domain'] = [('grant_id', '=', self.id)]
        action['context'] = {'default_grant_id': self.id}
        return action
    
    def _check_approval_chain_progress(self):
        for grant in self:
            if not grant.approval_step_ids:
                continue
            pending = grant.approval_step_ids.filtered(lambda s: s.state == 'pending')
            rejected = grant.approval_step_ids.filtered(lambda s: s.state == 'rejected')
            if rejected:
                grant.with_context(allow_workflow_state_change=True).write({'state': 'rejected'})
            elif not pending:
                grant.with_context(allow_workflow_state_change=True).write({'state': 'approved'})
                grant.message_post(body=_("All approval steps completed. Grant is Approved."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state') and vals['state'] != 'draft':
                raise AccessError(_('New grants must start in Draft.'))
        grants = super(NgoGrant, self).create(vals_list)
        for grant in grants:
            grant.message_post(body=_('Grant %s created') % grant.grant_name)
            grant._log_audit_change('create', vals_list[0] if vals_list else {})
        return grants

    def write(self, vals):
        """Enforce lifecycle rules and record immutable audit logs."""
        if 'state' in vals and not self.env.context.get('allow_workflow_state_change'):
            raise AccessError(_('Grant state can only be changed through the workflow actions.'))
        allowed_after_draft = {
            'state', 'active', 'close_date',
            'amendment_ids', 'disbursement_ids', 'grant_stage',
            'donor_reference', 'total_contributed_amount',
            'remaining_contribution_amount', 'disbursed_amount',
        }
        if not self.env.context.get('skip_donor_contribution_check'):
            for grant in self:
                permitted_fields = set(allowed_after_draft)
                blocked_fields = set(vals) - permitted_fields
                if grant.state != 'draft' and blocked_fields:
                    raise AccessError(
                        _('Grant details can only be changed while the grant is in Draft. '
                          'Use an amendment or disbursement for changes after Draft.')
                    )
        if 'state' in vals:
            for grant in self:
                if grant.state == 'closed' and vals['state'] != 'closed':
                    raise ValidationError(_('Closed grants cannot be modified.'))
        
        # Log old values for audit trail
        tracked_fields = ['approved_amount', 'state', 'start_date', 'end_date']
        old_vals = {}
        for grant in self:
            for f in tracked_fields:
                if f in vals:
                    old_vals[grant.id, f] = getattr(grant, f)

        res = super(NgoGrant, self).write(vals)

        for grant in self:
            for f in tracked_fields:
                if f in vals:
                    old_v = old_vals.get((grant.id, f))
                    new_v = getattr(grant, f)
                    if str(old_v) != str(new_v):
                        self.env['ngo.grant.audit.log'].sudo().create({
                            'grant_id': grant.id,
                            'user_id': self.env.user.id,
                            'timestamp': fields.Datetime.now(),
                            'model_name': 'ngo.grant',
                            'res_id': grant.id,
                            'field_name': f,
                            'field_description': self._fields[f].string if f in self._fields else f,
                            'old_value': str(old_v),
                            'new_value': str(new_v),
                            'action_type': 'write',
                        })
        return res

    def _log_audit_change(self, action_type, vals):
        for grant in self:
            self.env['ngo.grant.audit.log'].sudo().create({
                'grant_id': grant.id,
                'user_id': self.env.user.id,
                'timestamp': fields.Datetime.now(),
                'model_name': 'ngo.grant',
                'res_id': grant.id,
                'field_name': 'state',
                'field_description': 'Grant Creation',
                'old_value': '',
                'new_value': grant.state,
                'action_type': action_type,
            })
    
    def unlink(self):
        """Prevent deletion beyond Draft."""
        for grant in self:
            if grant.state != 'draft':
                raise ValidationError(_('Only draft grants can be deleted.'))
        return super(NgoGrant, self).unlink()
    
    def copy(self, default=None):
        """Create draft copy without reusing grant number."""
        if default is None:
            default = {}
        default = default.copy()
        default['grant_number'] = False
        default['state'] = 'draft'
        default['amendment_ids'] = False
        default['document_ids'] = False
        return super(NgoGrant, self).copy(default)

    @api.model
    def send_unspent_balance_reminders(self):
        """Cron: Send weekly reminders for grants with significant unspent balances near end date."""
        today = fields.Date.today()
        # Grants active and ending within 90 days with >10% remaining
        active_grants = self.search([
            ('state', '=', 'active'),
            ('end_date', '>=', today),
        ])
        template = self.env.ref('ngo_grant.email_template_unspent_balance', raise_if_not_found=False)
        for grant in active_grants:
            days_remaining = (grant.end_date - today).days
            if grant.approved_amount > 0:
                remaining_pct = (grant.remaining_amount / grant.approved_amount) * 100.0
            else:
                remaining_pct = 0.0
            # Send reminder if >10% unspent and within 90 days of end
            if remaining_pct > 10.0 and days_remaining <= 90:
                grant.message_post(
                    body=_(
                        "⚠️ <b>Unspent Balance Reminder</b>: Grant <b>%s</b> has <b>%.1f%%</b> "
                        "(%s %s) remaining and ends in <b>%d days</b> (%s). "
                        "Please review disbursement schedules."
                    ) % (
                        grant.grant_number,
                        remaining_pct,
                        grant.remaining_amount,
                        grant.currency_id.name,
                        days_remaining,
                        grant.end_date,
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
                if template and grant.user_id:
                    template.send_mail(grant.id, force_send=True, raise_exception=False)

    @api.model
    def check_grant_expiry(self):
        """Cron: Mark grants as expired and send expiry email notifications."""
        today = fields.Date.today()
        template = self.env.ref('ngo_grant.email_template_grant_expiry', raise_if_not_found=False)
        # Warn about grants expiring in the next 30 days
        expiring_grants = self.search([
            ('state', 'in', ['active', 'approved']),
            ('end_date', '>=', today),
        ])
        for grant in expiring_grants:
            days_remaining = (grant.end_date - today).days
            if days_remaining <= 30:
                grant.message_post(
                    body=_("Grant <b>%s</b> expires in <b>%d days</b> on %s.") % (
                        grant.grant_number, days_remaining, grant.end_date
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
                if template and grant.user_id:
                    template.send_mail(grant.id, force_send=True, raise_exception=False)

    @api.model
    def update_overdue_items(self):
        """Cron: Mark overdue compliance items."""
        today = fields.Date.today()
        overdue_compliance = self.env['ngo.grant.compliance'].search([
            ('state', 'not in', ['completed', 'cancelled']),
            ('due_date', '<', today),
        ])
        for item in overdue_compliance:
            item.message_post(
                body=_("Compliance item <b>%s</b> on grant <b>%s</b> is overdue (due: %s).") % (
                    item.name, item.grant_id.grant_number, item.due_date
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

