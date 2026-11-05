# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class NgoSubgrantAmendment(models.Model):
    _name = 'ngo.subgrant.amendment'
    _description = 'Subgrant Amendment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'amendment_number'
    _order = 'amendment_date desc, id desc'

    amendment_number = fields.Char(required=True, copy=False, default=lambda self: _('New'), tracking=True)
    amendment_name = fields.Char(string='Amendment Name', required=True, tracking=True)
    subgrant_id = fields.Many2one('ngo.subgrant', string='Subgrant', required=True, ondelete='cascade', tracking=True)
    currency_id = fields.Many2one(related='subgrant_id.currency_id', store=True, readonly=True)
    amendment_type = fields.Selection([
        ('budget_revision', 'Budget Revision'), ('extension', 'Extension (No-Cost)'),
        ('additional_funding', 'Additional Funding'), ('scope_change', 'Scope Change'),
        ('activity_revision', 'Activity Revision'), ('other', 'Other'),
    ], required=True, default='budget_revision', tracking=True)
    amendment_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    effective_date = fields.Date()
    amount_change = fields.Monetary(currency_field='currency_id', tracking=True)
    previous_approved_amount = fields.Monetary(currency_field='currency_id', compute='_compute_amounts', store=True)
    new_approved_amount = fields.Monetary(currency_field='currency_id', compute='_compute_amounts', store=True)
    original_end_date = fields.Date(required=True)
    new_end_date = fields.Date()
    description = fields.Text(required=True)
    amendment_reason = fields.Text()
    state = fields.Selection([('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='draft', required=True, tracking=True)
    approved_by = fields.Many2one('res.users', readonly=True)
    approval_date = fields.Date(readonly=True)

    @api.depends('subgrant_id.approved_amount', 'amount_change')
    def _compute_amounts(self):
        for rec in self:
            rec.previous_approved_amount = rec.subgrant_id.approved_amount
            rec.new_approved_amount = rec.previous_approved_amount + (rec.amount_change or 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('amendment_number', _('New')) == _('New'):
                vals['amendment_number'] = self.env['ir.sequence'].next_by_code('ngo.subgrant.amendment') or _('New')
            if vals.get('subgrant_id') and not vals.get('original_end_date'):
                vals['original_end_date'] = self.env['ngo.subgrant'].browse(vals['subgrant_id']).end_date
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        for rec in self:
            if rec.new_approved_amount <= 0:
                raise ValidationError(_('The amended subgrant amount must be greater than zero.'))
            reserved = sum(rec.subgrant_id.disbursement_ids.filtered(
                lambda item: item.state in ('approved', 'processed')
            ).mapped('amount'))
            if rec.new_approved_amount < reserved:
                raise ValidationError(_('The amended subgrant amount cannot be less than approved or processed disbursements.'))
            vals = {'approved_amount': rec.new_approved_amount}
            if rec.new_end_date:
                vals['end_date'] = rec.new_end_date
            rec.subgrant_id.write(vals)
            rec.write({'state': 'approved', 'approved_by': self.env.user.id, 'approval_date': fields.Date.today()})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class NgoSubgrantDisbursement(models.Model):
    _name = 'ngo.subgrant.disbursement'
    _description = 'Subgrant Disbursement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'disbursement_date desc, id desc'

    name = fields.Char(string='Disbursement Reference', required=True, copy=False, default=lambda self: _('New'), tracking=True)
    subgrant_id = fields.Many2one('ngo.subgrant', string='Subgrant', required=True, ondelete='cascade', tracking=True)
    currency_id = fields.Many2one(related='subgrant_id.currency_id', store=True, readonly=True)
    amount = fields.Monetary(string='Disbursement Amount', currency_field='currency_id', required=True, tracking=True)
    disbursement_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    payment_reference = fields.Char(tracking=True)
    description = fields.Text()
    state = fields.Selection([('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('processed', 'Processed'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='draft', required=True, tracking=True)
    approved_by = fields.Many2one('res.users', readonly=True)
    approval_date = fields.Date(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ngo.subgrant.disbursement') or _('New')
        return super().create(vals_list)

    @api.constrains('amount', 'subgrant_id', 'state')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Disbursement amount must be positive.'))
            if rec.state in ('approved', 'processed'):
                other_reservations = rec.subgrant_id.disbursement_ids.filtered(
                    lambda item: item.id != rec.id and item.state in ('approved', 'processed')
                )
                available = rec.subgrant_id.approved_amount - sum(other_reservations.mapped('amount'))
                if rec.amount > available:
                    raise ValidationError(_('Approved subgrant disbursements cannot exceed the subgrant approved amount.'))

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved', 'approved_by': self.env.user.id, 'approval_date': fields.Date.today()})

    def action_process(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only approved subgrant disbursements can be processed.'))
            rec.write({'state': 'processed'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class NgoSubgrantDocument(models.Model):
    _name = 'ngo.subgrant.document'
    _description = 'Subgrant Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'document_date desc, id desc'

    name = fields.Char(string='Document Name', required=True, tracking=True)
    subgrant_id = fields.Many2one('ngo.subgrant', string='Subgrant', required=True, ondelete='cascade', tracking=True)
    document_type = fields.Selection([
        ('agreement', 'Subgrant Agreement'), ('amendment', 'Amendment'),
        ('donor_approval', 'Donor Approval'), ('financial_report', 'Financial Report'),
        ('compliance', 'Compliance'), ('other', 'Other'),
    ], default='other', required=True, tracking=True)
    document_date = fields.Date(default=fields.Date.context_today, tracking=True)
    file = fields.Binary(string='File', attachment=True)
    file_name = fields.Char(string='File Name')
    description = fields.Text()


class NgoSubgrantDonorLine(models.Model):
    _name = 'ngo.subgrant.donor.line'
    _description = 'Subgrant Donor Allocation'
    _order = 'lead_donor desc, contribution_amount desc'

    subgrant_id = fields.Many2one('ngo.subgrant', string='Subgrant', required=True, ondelete='cascade')
    donor_id = fields.Many2one('ngo.grant.donor', string='Donor', required=True, ondelete='restrict')
    currency_id = fields.Many2one(related='subgrant_id.currency_id', store=True, readonly=True)
    contribution_amount = fields.Monetary(string='Contribution Amount', currency_field='currency_id')
    contribution_percentage = fields.Float(string='Contribution (%)', compute='_compute_percentage', inverse='_inverse_percentage', store=True, readonly=False)
    lead_donor = fields.Boolean(string='Lead Donor', default=False)
    donor_reference = fields.Char(string='Donor Reference')
    agreement_reference = fields.Char(string='Agreement Reference')
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('suspended', 'Suspended'), ('completed', 'Completed')], default='draft', required=True)

    @api.depends('contribution_amount', 'subgrant_id.approved_amount')
    def _compute_percentage(self):
        for line in self:
            amount = line.subgrant_id.approved_amount
            line.contribution_percentage = (line.contribution_amount / amount * 100.0) if amount else 0.0

    def _inverse_percentage(self):
        for line in self:
            if line.subgrant_id.approved_amount:
                line.contribution_amount = line.subgrant_id.approved_amount * line.contribution_percentage / 100.0

    @api.constrains('subgrant_id', 'donor_id')
    def _check_donor_unique(self):
        for line in self:
            if self.search_count([('subgrant_id', '=', line.subgrant_id.id), ('donor_id', '=', line.donor_id.id), ('id', '!=', line.id)]):
                raise ValidationError(_('A donor can only be listed once on the same subgrant.'))

    @api.constrains('subgrant_id', 'lead_donor')
    def _check_single_lead_donor(self):
        for line in self.filtered('lead_donor'):
            if self.search_count([('subgrant_id', '=', line.subgrant_id.id), ('lead_donor', '=', True), ('id', '!=', line.id)]):
                raise ValidationError(_('Only one lead donor can be assigned to a subgrant.'))

    @api.constrains('contribution_percentage')
    def _check_percentage(self):
        for line in self:
            if line.contribution_percentage < 0 or line.contribution_percentage > 100:
                raise ValidationError(_('Contribution percentage must be between 0 and 100.'))
