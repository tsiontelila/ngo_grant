# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class NgoSubgrant(models.Model):
    _name = 'ngo.subgrant'
    _description = 'NGO Subgrant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'grant_name'
    _order = 'grant_number desc'

    grant_number = fields.Char(string='Subgrant Number', required=True, copy=False, tracking=True)
    grant_name = fields.Char(string='Subgrant Name', required=True, tracking=True)
    short_name = fields.Char(tracking=True)
    description = fields.Text()
    grant_id = fields.Many2one('ngo.grant', string='Parent Grant', required=True, ondelete='cascade', tracking=True)
    currency_id = fields.Many2one(related='grant_id.currency_id', store=True, readonly=True)
    approved_amount = fields.Monetary(string='Approved Amount', currency_field='currency_id', required=True, tracking=True)
    disbursed_amount = fields.Monetary(currency_field='currency_id', compute='_compute_financials', store=True)
    remaining_amount = fields.Monetary(currency_field='currency_id', compute='_compute_financials', store=True)
    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(required=True, tracking=True)
    agreement_date = fields.Date(tracking=True)
    close_date = fields.Date(tracking=True)
    funding_type_id = fields.Many2one('ngo.funding.type', string='Funding Type', tracking=True)
    sector_id = fields.Many2one('ngo.sector', string='Sector', tracking=True)
    program_area_id = fields.Many2one('ngo.program.area', string='Program Area', tracking=True)
    company_id = fields.Many2one(related='grant_id.company_id', store=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('submitted', 'Submitted'), ('under_review', 'Under Review'),
        ('approved', 'Approved'), ('active', 'Active'), ('completed', 'Completed'),
        ('closed', 'Closed'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled'), ('suspended', 'Suspended'),
    ], default='draft', required=True, tracking=True)
    active = fields.Boolean(default=True)
    amendment_ids = fields.One2many('ngo.subgrant.amendment', 'subgrant_id', string='Amendments')
    disbursement_ids = fields.One2many('ngo.subgrant.disbursement', 'subgrant_id', string='Disbursements')
    compliance_ids = fields.One2many('ngo.grant.compliance', 'subgrant_id', string='Compliance')
    donor_line_ids = fields.One2many('ngo.subgrant.donor.line', 'subgrant_id', string='Subgrant Donor Allocations')
    document_ids = fields.One2many('ngo.subgrant.document', 'subgrant_id', string='Documents')

    @api.depends('approved_amount', 'disbursement_ids.amount', 'disbursement_ids.state')
    def _compute_financials(self):
        for record in self:
            record.disbursed_amount = sum(record.disbursement_ids.filtered(lambda d: d.state == 'processed').mapped('amount'))
            reserved = sum(record.disbursement_ids.filtered(lambda d: d.state in ('approved', 'processed')).mapped('amount'))
            record.remaining_amount = record.approved_amount - reserved

    @api.constrains('grant_number')
    def _check_number_unique(self):
        for record in self:
            if self.search_count([('grant_number', '=', record.grant_number), ('id', '!=', record.id)]):
                raise ValidationError(_('Subgrant number must be unique.'))

    @api.constrains('start_date', 'end_date', 'approved_amount')
    def _check_values(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_('Start Date must be before End Date.'))
            if record.approved_amount <= 0:
                raise ValidationError(_('Approved Amount must be greater than zero.'))

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed', 'close_date': fields.Date.today(), 'active': False})

    def action_view_amendments(self):
        self.ensure_one()
        action = self.env.ref('ngo_grant.action_subgrant_amendment').read()[0]
        action.update(domain=[('subgrant_id', '=', self.id)], context={'default_subgrant_id': self.id})
        return action

    def action_view_disbursements(self):
        self.ensure_one()
        action = self.env.ref('ngo_grant.action_subgrant_disbursement').read()[0]
        action.update(domain=[('subgrant_id', '=', self.id)], context={'default_subgrant_id': self.id})
        return action

    def action_view_compliance(self):
        self.ensure_one()
        action = self.env.ref('ngo_grant.action_compliance').read()[0]
        action.update(domain=[('subgrant_id', '=', self.id)], context={'default_subgrant_id': self.id, 'default_grant_id': self.grant_id.id})
        return action
