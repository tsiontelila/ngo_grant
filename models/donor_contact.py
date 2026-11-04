# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class NgoGrantContact(models.Model):
    """NGO Grant Contact model.
    
    Tracks donor contacts such as Program Officer, Finance Officer, Contract Officer, and Monitoring Officer.
    Linked to res.partner.
    """
    
    _name = 'ngo.grant.contact'
    _description = 'NGO Grant Donor Contact'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'donor_id, name'
    
    # Identification
    donor_id = fields.Many2one(
        'ngo.grant.donor',
        string='Donor',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Associated donor',
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact Person',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='Contact person from res.partner',
    )
    
    name = fields.Char(
        string='Name',
        related='partner_id.name',
        store=True,
        readonly=True,
    )
    
    email = fields.Char(
        string='Email',
        compute='_compute_contact_info',
        inverse='_inverse_email',
        store=False,
    )
    
    phone = fields.Char(
        string='Phone',
        compute='_compute_contact_info',
        inverse='_inverse_phone',
        store=False,
    )
    
    # Role
    contact_role = fields.Selection([
        ('program_manager', 'Program Manager'),
        ('grant_manager', 'Grant Manager'),
        ('finance_manager', 'Finance Manager'),
        ('procurement_manager', 'Procurement Manager'),
        ('compliance_officer', 'Compliance Officer'),
        ('monitoring_officer', 'Monitoring Officer'),
        ('country_director', 'Country Director'),
        ('technical_advisor', 'Technical Advisor'),
        ('legal_representative', 'Legal Representative'),
        ('other', 'Other'),
    ],
        string='Contact Role',
        required=True,
        tracking=True,
        help='Role of this contact person',
    )
    
    # Contact Details
    department = fields.Char(
        string='Department',
        tracking=True,
        help='Contact department',
    )
    
    position = fields.Char(
        string='Position',
        tracking=True,
        help='Contact position/title',
    )
    
    # Communication Preferences
    preferred_language = fields.Selection([
        ('english', 'English'),
        ('french', 'French'),
        ('spanish', 'Spanish'),
        ('arabic', 'Arabic'),
        ('amharic', 'Amharic'),
    ],
        string='Preferred Language',
        tracking=True,
        help='Preferred language for communication',
    )
    
    preferred_channel = fields.Selection([
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('video', 'Video Conference'),
        ('in_person', 'In Person'),
    ],
        string='Preferred Channel',
        tracking=True,
        help='Preferred communication channel',
    )
    
    timezone = fields.Selection([
        ('utc', 'UTC'),
        ('utc+3', 'UTC+3'),
        ('utc+5', 'UTC+5'),
        ('utc-5', 'UTC-5'),
        ('utc-8', 'UTC-8'),
    ],
        string='Timezone',
        tracking=True,
        help='Contact timezone',
    )
    
    # Responsibilities
    primary_contact = fields.Boolean(
        string='Primary Contact',
        default=False,
        tracking=True,
        help='Whether this is the primary contact for the donor',
    )
    
    financial_contact = fields.Boolean(
        string='Financial Contact',
        default=False,
        tracking=True,
        help='Whether this contact handles financial matters',
    )
    
    reporting_contact = fields.Boolean(
        string='Reporting Contact',
        default=False,
        tracking=True,
        help='Whether this contact handles reporting',
    )
    
    procurement_contact = fields.Boolean(
        string='Procurement Contact',
        default=False,
        tracking=True,
        help='Whether this contact handles procurement',
    )
    
    compliance_contact = fields.Boolean(
        string='Compliance Contact',
        default=False,
        tracking=True,
        help='Whether this contact handles compliance',
    )
    
    # Status
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='Whether this contact is active',
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this contact',
    )
    
    @api.depends('partner_id')
    def _compute_contact_info(self):
        """Compute email and phone from partner."""
        for contact in self:
            contact.email = contact.partner_id.email if contact.partner_id else ''
            contact.phone = contact.partner_id.phone if contact.partner_id else ''
    
    def _inverse_email(self):
        """Write email back to partner."""
        for contact in self:
            if contact.partner_id:
                contact.partner_id.email = contact.email
    
    def _inverse_phone(self):
        """Write phone back to partner."""
        for contact in self:
            if contact.partner_id:
                contact.partner_id.phone = contact.phone
    
    @api.constrains('donor_id', 'partner_id')
    def _check_contact_unique(self):
        """Ensure contact is unique per donor."""
        for contact in self:
            if contact.donor_id and contact.partner_id:
                existing = self.search([
                    ('donor_id', '=', contact.donor_id.id),
                    ('partner_id', '=', contact.partner_id.id),
                    ('id', '!=', contact.id),
                ])
                if existing:
                    raise ValidationError(_('A contact can only be linked once to a donor!'))
    
    @api.constrains('primary_contact')
    def _check_primary_contact(self):
        """Ensure only one primary contact per donor."""
        for contact in self:
            if contact.primary_contact:
                other_primary = self.search([
                    ('donor_id', '=', contact.donor_id.id),
                    ('primary_contact', '=', True),
                    ('id', '!=', contact.id),
                ])
                if other_primary:
                    raise ValidationError(_('Only one primary contact is allowed per donor.'))
    
    def name_get(self):
        """Custom name_get to show role and contact name."""
        result = []
        for contact in self:
            name = _('%(role)s: %(name)s') % {
                'role': dict(self._fields['contact_role'].selection).get(contact.contact_role),
                'name': contact.name,
            }
            result.append((contact.id, name))
        return result
