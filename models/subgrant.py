# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .workflow_access import check_cancellation_access, check_reset_access


class NgoSubgrant(models.Model):
    _name = 'ngo.subgrant'
    _description = 'NGO Subgrant'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ngo.cancellation.access.mixin']
    _rec_name = 'grant_name'
    _order = 'grant_number desc'

    grant_number = fields.Char(string='Subgrant Number', required=True, copy=False, tracking=True)
    grant_name = fields.Char(string='Subgrant Name', required=True, tracking=True)
    short_name = fields.Char(tracking=True)
    description = fields.Text(tracking=True)
    grant_id = fields.Many2one('ngo.grant', string='Parent Grant', required=True, ondelete='cascade', tracking=True)
    currency_id = fields.Many2one(related='grant_id.currency_id', store=True, readonly=True)
    approved_amount = fields.Monetary(string='Approved Amount', currency_field='currency_id', required=True, tracking=True)
    allocation_amount = fields.Monetary(string='Allocation Amount', currency_field='currency_id', required=True, default=0.0, tracking=True)
    allocation_percentage = fields.Float(
        string='Allocation (%)', compute='_compute_allocation_percentage',
        inverse='_inverse_allocation_percentage', digits=(16, 2), tracking=True,
        help='Enter a percentage of the selected grant remaining amount.',
    )
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
    active = fields.Boolean(default=True, tracking=True)
    can_edit_approved = fields.Boolean(compute='_compute_can_edit_approved')
    amendment_ids = fields.One2many('ngo.subgrant.amendment', 'subgrant_id', string='Amendments')
    disbursement_ids = fields.One2many('ngo.subgrant.disbursement', 'subgrant_id', string='Disbursements')
    compliance_ids = fields.One2many('ngo.grant.compliance', 'subgrant_id', string='Compliance')
    document_ids = fields.One2many('ngo.subgrant.document', 'subgrant_id', string='Documents')
    grant_document_ids = fields.One2many('ngo.grant.document', 'subgrant_id', string='Documents')

    @api.depends_context('uid')
    def _compute_can_edit_approved(self):
        for record in self:
            record.can_edit_approved = False

    def action_cancel(self):
        check_cancellation_access(self)
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({'state': 'cancelled'})
        self.sudo().message_post(body=_('Subgrant cancelled.'))

    def action_reset_cancelled(self):
        check_reset_access(self)
        if any(record.state != 'cancelled' for record in self):
            raise ValidationError(_('Only cancelled subgrants can be reset to Draft.'))
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({'state': 'draft', 'active': True})
        self.sudo().message_post(body=_('Cancelled subgrant reset to Draft for revision.'))

    def init(self):
        self.env.cr.execute(
            f'UPDATE "{self._table}" SET allocation_amount = approved_amount WHERE allocation_amount IS NULL OR allocation_amount = 0'
        )

    @api.depends(
        'allocation_amount', 'grant_id.approved_amount',
        'grant_id.disbursement_ids.amount', 'grant_id.disbursement_ids.state',
    )
    def _compute_allocation_percentage(self):
        for record in self:
            remaining = record.grant_id.remaining_amount
            record.allocation_percentage = (record.allocation_amount / remaining * 100.0) if remaining > 0 else 0.0

    def _inverse_allocation_percentage(self):
        for record in self:
            remaining = record.grant_id.remaining_amount
            if record.grant_id and remaining > 0 and record.allocation_percentage >= 0:
                amount = record.currency_id.round(remaining * record.allocation_percentage / 100.0)
                record.allocation_amount = amount
                record.approved_amount = amount

    @api.onchange('allocation_percentage')
    def _onchange_allocation_percentage(self):
        for record in self:
            remaining = record.grant_id.remaining_amount if record.grant_id else 0.0
            if remaining > 0 and record.allocation_percentage >= 0:
                amount = record.currency_id.round(remaining * record.allocation_percentage / 100.0)
                record.allocation_amount = amount
                record.approved_amount = amount

    @api.onchange('allocation_amount')
    def _onchange_allocation_amount(self):
        for record in self:
            if record.allocation_amount is not False:
                record.approved_amount = record.allocation_amount

    @api.onchange('approved_amount')
    def _onchange_approved_amount_allocation(self):
        for record in self:
            if record.approved_amount is not False:
                record.allocation_amount = record.approved_amount

    @api.onchange('grant_id')
    def _onchange_grant_id_allocation_percentage(self):
        for record in self:
            if record.grant_id and record.allocation_percentage:
                remaining = record.grant_id.remaining_amount
                amount = record.currency_id.round(remaining * record.allocation_percentage / 100.0)
                record.allocation_amount = amount
                record.approved_amount = amount

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            grant = self.env['ngo.grant'].browse(vals.get('grant_id')) if vals.get('grant_id') else self.env['ngo.grant']
            if vals.get('allocation_percentage') and grant:
                amount = grant.currency_id.round(grant.remaining_amount * vals['allocation_percentage'] / 100.0)
                vals['allocation_amount'] = amount
                vals['approved_amount'] = amount
            elif not vals.get('allocation_amount') and vals.get('approved_amount') is not None:
                vals['allocation_amount'] = vals['approved_amount']
            if vals.get('allocation_amount') and not vals.get('approved_amount'):
                vals['approved_amount'] = vals['allocation_amount']
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        locked_states = {'approved', 'active', 'suspended', 'completed', 'closed', 'rejected', 'cancelled'}
        if not self.env.su:
            for record in self:
                if record.state in locked_states:
                    if vals.get('state') == 'draft' and record.state != 'cancelled':
                        raise AccessError(_('An approved subgrant must be cancelled before it can be reset to Draft.'))
                    if set(vals) - {'state'}:
                        raise AccessError(_('Approved subgrant details are locked. Cancel the subgrant and reset it to Draft before editing.'))
        if 'allocation_percentage' in vals and 'allocation_amount' not in vals:
            for record in self:
                grant = self.env['ngo.grant'].browse(vals.get('grant_id')) if vals.get('grant_id') else record.grant_id
                if grant:
                    amount = grant.currency_id.round(grant.remaining_amount * vals['allocation_percentage'] / 100.0)
                    vals['allocation_amount'] = amount
                    vals.setdefault('approved_amount', amount)
                    break
        elif 'allocation_amount' in vals and 'approved_amount' not in vals:
            vals['approved_amount'] = vals['allocation_amount']
        elif 'approved_amount' in vals and 'allocation_amount' not in vals:
            vals['allocation_amount'] = vals['approved_amount']
        return super().write(vals)

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

    @api.constrains('start_date', 'end_date', 'approved_amount', 'allocation_amount', 'grant_id')
    def _check_values(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_('Start Date must be before End Date.'))
            if record.approved_amount <= 0:
                raise ValidationError(_('Approved Amount must be greater than zero.'))
            if record.allocation_amount <= 0 or record.approved_amount > record.allocation_amount:
                raise ValidationError(_('Approved Amount must be positive and cannot exceed the subgrant allocation amount.'))
            total_allocated = sum(record.grant_id.subgrant_ids.mapped('allocation_amount'))
            if record.grant_id.currency_id.compare_amounts(total_allocated, record.grant_id.remaining_amount) > 0:
                raise ValidationError(_('Total subgrant allocations cannot exceed the parent grant remaining amount.'))
            if record.allocation_percentage < 0 or record.allocation_percentage > 100:
                raise ValidationError(_('Allocation percentage must be between 0 and 100.'))

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_activate(self):
        self.sudo().write({'state': 'active'})

    def action_close(self):
        self.sudo().write({'state': 'closed', 'close_date': fields.Date.today(), 'active': False})

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
        action.update(domain=[('subgrant_id', '=', self.id)], context={'default_subgrant_id': self.id})
        return action
