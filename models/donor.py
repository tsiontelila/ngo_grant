# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class NgoGrantDonor(models.Model):
    """NGO Grant Donor model.
    
    Represents a donor organization participating in one or more grant agreements.
    Extends res.partner using _inherits pattern as per ADR-016.
    """
    
    _name = 'ngo.grant.donor'
    _description = 'NGO Grant Donor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'res.partner': 'partner_id'}
    _rec_name = 'donor_code'
    _order = 'donor_code'
    
    # Identification
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Linked partner record',
    )
    
    donor_code = fields.Char(
        string='Donor Code',
        required=True,
        copy=False,
        tracking=True,
        help='Unique donor code',
    )
    
    donor_type = fields.Selection([
        ('bilateral', 'Bilateral'),
        ('multilateral', 'Multilateral'),
        ('private', 'Private Foundation'),
        ('corporate', 'Corporate'),
        ('individual', 'Individual'),
        ('government', 'Government'),
        ('un_agency', 'UN Agency'),
        ('ngo', 'NGO'),
    ],
        string='Donor Type',
        required=True,
        tracking=True,
        help='Type of donor',
    )
    
    donor_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('blacklisted', 'Blacklisted'),
    ],
        string='Donor Status',
        required=True,
        default='active',
        tracking=True,
        help='Current donor status',
    )
    
    # Organization
    donor_category_id = fields.Many2one(
        'ngo.grant.donor.category',
        string='Donor Category',
        tracking=True,
        help='Primary donor category classification',
    )
    
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        tracking=True,
        help='Donor country',
    )
    
    preferred_currency_id = fields.Many2one(
        'res.currency',
        string='Preferred Currency',
        tracking=True,
        help='Preferred currency for funding',
    )
    
    # Reporting
    reporting_language = fields.Selection([
        ('english', 'English'),
        ('french', 'French'),
        ('spanish', 'Spanish'),
        ('arabic', 'Arabic'),
        ('amharic', 'Amharic'),
    ],
        string='Reporting Language',
        tracking=True,
        help='Preferred language for donor reports',
    )
    
    reporting_frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
    ],
        string='Reporting Frequency',
        tracking=True,
        help='Standard reporting frequency',
    )
    
    reporting_template_id = fields.Many2one(
        'ir.ui.view',
        string='Reporting Template',
        domain=[('type', '=', 'qweb')],
        tracking=True,
        help='QWeb template for donor reports',
    )
    
    # Compliance
    due_diligence_completed = fields.Boolean(
        string='Due Diligence Completed',
        tracking=True,
        help='Whether due diligence has been completed',
    )
    
    due_diligence_date = fields.Date(
        string='Due Diligence Date',
        tracking=True,
        help='Date when due diligence was completed',
    )
    
    compliance_notes = fields.Text(
        string='Compliance Notes',
        tracking=True,
        help='Notes regarding donor compliance requirements',
    )
    
    # Monitoring
    grant_count = fields.Integer(
        string='Grant Count',
        compute='_compute_grant_count',
        store=True,
        help='Number of grants from this donor',
    )
    
    active_grant_count = fields.Integer(
        string='Active Grant Count',
        compute='_compute_active_grant_count',
        store=True,
        help='Number of active grants',
    )
    
    total_funding = fields.Float(
        string='Total Funding',
        compute='_compute_total_funding',
        store=True,
        help='Total funding amount across all grants',
    )
    
    active_project_count = fields.Integer(
        string='Active Project Count',
        compute='_compute_active_project_count',
        store=True,
        help='Number of active projects funded by this donor',
    )
    
    contact_count = fields.Integer(
        string='Contact Count',
        compute='_compute_contact_count',
        store=True,
        help='Number of contacts for this donor',
    )
    
    amendment_count = fields.Integer(
        string='Amendment Count',
        compute='_compute_amendment_count',
        store=True,
        help='Number of amendments across all grants',
    )
    
    disbursement_count = fields.Integer(
        string='Disbursement Count',
        compute='_compute_disbursement_count',
        store=True,
        help='Number of disbursements across all grants',
    )
    
    compliance_count = fields.Integer(
        string='Compliance Count',
        compute='_compute_compliance_count',
        store=True,
        help='Number of compliance items across all grants',
    )
    
    reporting_count = fields.Integer(
        string='Reporting Count',
        compute='_compute_reporting_count',
        store=True,
        help='Number of reporting schedules across all grants',
    )
    
    # Relationships
    donor_line_ids = fields.One2many(
        'ngo.grant.donor.line',
        'donor_id',
        string='Grant Participations',
        help='Grants where this donor participates',
    )
    
    contact_ids = fields.One2many(
        'ngo.grant.contact',
        'donor_id',
        string='Contacts',
        help='Donor contact persons',
    )
    
    @api.constrains('donor_code')
    def _check_donor_code_unique(self):
        """Ensure donor code is unique."""
        for donor in self:
            if donor.donor_code:
                existing = self.search([
                    ('donor_code', '=', donor.donor_code),
                    ('id', '!=', donor.id),
                ])
                if existing:
                    raise ValidationError(_('Donor code must be unique!'))
    
    @api.depends('donor_line_ids')
    def _compute_grant_count(self):
        """Compute total grant count."""
        for donor in self:
            donor.grant_count = len(donor.donor_line_ids.mapped('grant_id'))
    
    @api.depends('donor_line_ids', 'donor_line_ids.grant_id', 'donor_line_ids.grant_id.state')
    def _compute_active_grant_count(self):
        """Compute active grant count."""
        for donor in self:
            donor.active_grant_count = len(donor.donor_line_ids.filtered(
                lambda l: l.grant_id.state == 'active'
            ).mapped('grant_id'))
    
    @api.depends('donor_line_ids')
    def _compute_total_funding(self):
        """Compute total funding across all grants."""
        for donor in self:
            donor.total_funding = sum(donor.donor_line_ids.mapped('contribution_amount'))
    
    @api.depends('donor_line_ids', 'donor_line_ids.grant_id', 'donor_line_ids.grant_id.state', 'donor_line_ids.grant_id.project_ids')
    def _compute_active_project_count(self):
        """Compute active project count."""
        for donor in self:
            active_grants = donor.donor_line_ids.filtered(
                lambda l: l.grant_id.state == 'active'
            ).mapped('grant_id')
            donor.active_project_count = len(active_grants.mapped('project_ids.project_id'))
    
    @api.depends('contact_ids')
    def _compute_contact_count(self):
        """Compute contact count."""
        for donor in self:
            donor.contact_count = len(donor.contact_ids)
    
    @api.depends('donor_line_ids')
    def _compute_amendment_count(self):
        """Compute amendment count across all grants."""
        for donor in self:
            grants = donor.donor_line_ids.mapped('grant_id')
            donor.amendment_count = sum(len(grant.amendment_ids) for grant in grants)
    
    @api.depends('donor_line_ids')
    def _compute_disbursement_count(self):
        """Compute disbursement count across all grants."""
        for donor in self:
            grants = donor.donor_line_ids.mapped('grant_id')
            donor.disbursement_count = sum(len(grant.disbursement_ids) for grant in grants)
    
    @api.depends('donor_line_ids')
    def _compute_compliance_count(self):
        """Compute compliance count across all grants."""
        for donor in self:
            grants = donor.donor_line_ids.mapped('grant_id')
            donor.compliance_count = sum(len(grant.compliance_ids) for grant in grants)
    
    @api.depends('donor_line_ids')
    def _compute_reporting_count(self):
        """Compute reporting count across all grants."""
        for donor in self:
            grants = donor.donor_line_ids.mapped('grant_id')
            donor.reporting_count = sum(len(grant.reporting_schedule_ids) for grant in grants)
    
    @api.constrains('due_diligence_date')
    def _check_due_diligence_date(self):
        """Validate due diligence date."""
        for donor in self:
            if donor.due_diligence_completed and not donor.due_diligence_date:
                raise ValidationError(_('Due Diligence Date is required when Due Diligence is marked as completed.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create donor with auto-generated code and partner record."""
        for vals in vals_list:
            if not vals.get('donor_code'):
                vals['donor_code'] = self.env['ir.sequence'].next_by_code('ngo.grant.donor') or 'DONOR-NEW'
            if not vals.get('partner_id'):
                # Create partner if not provided
                partner_vals = {
                    'name': vals.get('name', vals.get('donor_code', 'New Donor')),
                    'email': vals.get('email'),
                    'phone': vals.get('phone'),
                    'street': vals.get('street'),
                    'city': vals.get('city'),
                    'country_id': vals.get('country_id'),
                    'is_company': True,
                }
                # Donor creation should not require access to res.users. The
                # linked contact is a technical record owned by this donor.
                partner = self.env['res.partner'].sudo().create(partner_vals)
                vals['partner_id'] = partner.id
        donors = super(NgoGrantDonor, self).create(vals_list)
        for donor in donors:
            donor.message_post(
                body=_('Donor %s created') % donor.donor_code
            )
        return donors
    
    def write(self, vals):
        """Write with chatter message for status changes."""
        if 'donor_status' in vals:
            for donor in self:
                if donor.donor_status != vals['donor_status']:
                    donor.message_post(
                        body=_('Status changed from %s to %s') % (
                            donor.donor_status,
                            vals['donor_status']
                        )
                    )
        return super(NgoGrantDonor, self).write(vals)
    
    # Business Methods
    def action_activate(self):
        """Activate donor."""
        self.write({'donor_status': 'active'})
        self.message_post(body=_('Donor activated.'))
    
    def action_set_inactive(self):
        """Set donor to inactive status."""
        self.write({'donor_status': 'inactive'})
        self.message_post(body=_('Donor set to inactive.'))
    
    def action_suspend(self):
        """Suspend donor."""
        self.write({'donor_status': 'suspended'})
        self.message_post(body=_('Donor suspended.'))
    
    def action_blacklist(self):
        """Blacklist donor."""
        self.write({'donor_status': 'blacklisted'})
        self.message_post(body=_('Donor blacklisted.'))
    
    def action_restore(self):
        """Restore blacklisted donor to active status."""
        self.write({'donor_status': 'active'})
        self.message_post(body=_('Donor restored to active status.'))
    
    def action_view_grants(self):
        """View all grants for this donor."""
        self.ensure_one()
        grants = self.donor_line_ids.mapped('grant_id')
        action = self.env.ref('ngo_grant.action_grant').read()[0]
        action['domain'] = [('id', 'in', grants.ids)]
        action['context'] = {'default_donor_line_ids': [(0, 0, {'donor_id': self.id})]}
        return action
    
    def action_view_projects(self):
        """View all projects funded by this donor."""
        self.ensure_one()
        grants = self.donor_line_ids.mapped('grant_id')
        projects = grants.mapped('project_ids.project_id')
        action = self.env.ref('project.open_view_project_all_config').read()[0]
        action['domain'] = [('id', 'in', projects.ids)]
        return action
    
    def get_statistics(self):
        """Get donor statistics for dashboard."""
        self.ensure_one()
        return {
            'grant_count': self.grant_count,
            'active_grant_count': self.active_grant_count,
            'total_funding': self.total_funding,
            'active_project_count': self.active_project_count,
        }
