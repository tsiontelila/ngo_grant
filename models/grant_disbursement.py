# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError, UserError


class NgoGrantDisbursement(models.Model):
    """NGO Grant Disbursement model.

    Tracks individual disbursement transactions for grants with multi-level
    approval workflow and processing status.
    """

    _name = 'ngo.grant.disbursement'
    _description = 'NGO Grant Disbursement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'disbursement_date desc, id desc'

    name = fields.Char(
        string='Disbursement Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
        help='Unique disbursement reference',
    )

    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Grant this disbursement belongs to',
    )

    currency_id = fields.Many2one(
        related='grant_id.currency_id',
        string='Currency',
        readonly=True,
        store=True,
    )

    amount = fields.Monetary(
        string='Disbursement Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
        help='Amount disbursed',
    )

    disbursement_date = fields.Date(
        string='Disbursement Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help='Date when disbursement was made',
    )

    # Keep the legacy code column so existing disbursement records remain intact.
    disbursement_type = fields.Char(string='Legacy Disbursement Type Code', readonly=True, copy=False)
    disbursement_type_id = fields.Many2one(
        'ngo.grant.disbursement.type',
        string='Disbursement Type',
        tracking=True,
        ondelete='restrict',
        compute='_compute_disbursement_type_id',
        inverse='_inverse_disbursement_type_id',
        store=True,
    )
    approval_line_ids = fields.One2many(
        'ngo.grant.disbursement.approval.step', 'disbursement_id',
        string='Approval Chain', copy=False,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('level1_approved', 'Partially Approved'),
        ('approved', 'Fully Approved'),
        ('processed', 'Processed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        help='Disbursement workflow status',
    )

    # ── Multi-level Approval ─────────────────────────────────────────────────
    level1_approver_id = fields.Many2one(
        'res.users',
        string='Level 1 Approver',
        domain=lambda self: self._get_ngo_approver_domain(),
        tracking=True,
        help='First-level approver (e.g. Finance Officer)',
    )
    level1_approved_by = fields.Many2one('res.users', string='L1 Approved By', readonly=True)
    level1_approved_date = fields.Datetime(string='L1 Approval Date', readonly=True)
    level1_notes = fields.Text(string='Level 1 Notes')

    level2_approver_id = fields.Many2one(
        'res.users',
        string='Level 2 Approver',
        domain=lambda self: self._get_ngo_approver_domain(),
        tracking=True,
        help='Second-level approver (e.g. Finance Manager / CFO)',
    )
    level2_approved_by = fields.Many2one('res.users', string='L2 Approved By', readonly=True)
    level2_approved_date = fields.Datetime(string='L2 Approval Date', readonly=True)
    level2_notes = fields.Text(string='Level 2 Notes')

    rejection_reason = fields.Text(string='Rejection Reason')

    # ── Other Fields ─────────────────────────────────────────────────────────
    description = fields.Text(string='Description', help='Description of this disbursement')
    notes = fields.Text(string='Notes', help='Internal notes')

    payment_reference = fields.Char(
        string='Payment Reference',
        tracking=True,
        help='Bank or payment reference',
    )

    active = fields.Boolean(string='Active', default=True, tracking=True)

    @api.depends('disbursement_type')
    def _compute_disbursement_type_id(self):
        Type = self.env['ngo.grant.disbursement.type']
        for record in self:
            record.disbursement_type_id = Type.search(
                [('code', '=', record.disbursement_type or 'installment')], limit=1,
            )

    def _inverse_disbursement_type_id(self):
        for record in self:
            record.disbursement_type = record.disbursement_type_id.code or False

    @api.onchange('disbursement_type_id')
    def _onchange_disbursement_type_id(self):
        for record in self:
            commands = [fields.Command.clear()]
            if record.disbursement_type_id:
                commands.extend(fields.Command.create({
                    'sequence': step.sequence,
                    'name': step.name,
                    'approver_id': step.approver_id.id,
                    'group_id': step.group_id.id,
                }) for step in record.disbursement_type_id.approval_step_ids.sorted(
                    key=lambda item: (item.sequence, item.id)
                ))
            record.approval_line_ids = commands

    def _get_ngo_approver_domain(self):
        approver_group = self.env.ref(
            'ngo_grant.group_ngo_approver', raise_if_not_found=False
        )
        return [('all_group_ids', 'in', approver_group.ids)] if approver_group else [('id', '=', False)]

    def _is_ngo_approver(self, user):
        approver_group = self.env.ref(
            'ngo_grant.group_ngo_approver', raise_if_not_found=False
        )
        return bool(
            user
            and approver_group
            and approver_group in user.all_group_ids
        )

    @api.constrains('level1_approver_id', 'level2_approver_id')
    def _check_assigned_approvers(self):
        for record in self:
            for approver in (record.level1_approver_id, record.level2_approver_id):
                if approver and not record._is_ngo_approver(approver):
                    raise ValidationError(
                        _('Level 1 and Level 2 approvers must have the NGO Grant Approver role.')
                    )

    # ── Sequence ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-assign disbursement reference number."""
        approval_values = []
        prepared_values = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get('state') and vals['state'] != 'draft':
                raise AccessError(_('New disbursements must start in Draft.'))
            vals.pop('approval_line_ids', None)
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ngo.grant.disbursement') or _('New')
            if not vals.get('disbursement_type_id'):
                legacy_code = vals.get('disbursement_type') or 'installment'
                disbursement_type = self.env['ngo.grant.disbursement.type'].search(
                    [('code', '=', legacy_code)], limit=1,
                )
                vals['disbursement_type_id'] = disbursement_type.id or False
            if vals.get('disbursement_type_id'):
                disbursement_type = self.env['ngo.grant.disbursement.type'].browse(vals['disbursement_type_id'])
                vals['disbursement_type'] = disbursement_type.code
            approval_values.append(disbursement_type.approval_step_ids.sorted(
                key=lambda item: (item.sequence, item.id)
            ) if vals.get('disbursement_type_id') else self.env['ngo.grant.disbursement.type.approval.step'])
            prepared_values.append(vals)
        records = super().create(prepared_values)
        ApprovalStep = self.env['ngo.grant.disbursement.approval.step'].sudo()
        for record, templates in zip(records, approval_values):
            ApprovalStep.create([{
                'disbursement_id': record.id,
                'sequence': step.sequence,
                'name': step.name,
                'approver_id': step.approver_id.id,
                'group_id': step.group_id.id,
            } for step in templates])
        return records

    def write(self, vals):
        vals = dict(vals)
        if 'state' in vals and not self.env.context.get('allow_disbursement_state_change'):
            raise AccessError(_('Disbursement state can only be changed through its workflow actions.'))
        vals.pop('approval_line_ids', None)
        if vals.get('disbursement_type_id'):
            disbursement_type = self.env['ngo.grant.disbursement.type'].browse(vals['disbursement_type_id'])
            vals = dict(vals, disbursement_type=disbursement_type.code)
        changing_type = 'disbursement_type_id' in vals
        if changing_type and any(record.state != 'draft' for record in self):
            raise UserError(_('The disbursement type can only be changed while the disbursement is in Draft.'))
        result = super().write(vals)
        if changing_type:
            ApprovalStep = self.env['ngo.grant.disbursement.approval.step'].sudo()
            for record in self:
                record.approval_line_ids.sudo().unlink()
                templates = record.disbursement_type_id.approval_step_ids.sorted(
                    key=lambda item: (item.sequence, item.id)
                )
                ApprovalStep.create([{
                    'disbursement_id': record.id,
                    'sequence': step.sequence,
                    'name': step.name,
                    'approver_id': step.approver_id.id,
                    'group_id': step.group_id.id,
                } for step in templates])
        return result

    # ── Workflow Actions ──────────────────────────────────────────────────────
    def action_submit(self):
        """Submit to the first configured approver."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only Draft disbursements can be submitted.'))
            if not rec.approval_line_ids:
                raise UserError(_('Assign at least one approver to this disbursement type before submitting.'))
        self.with_context(allow_disbursement_state_change=True).write({'state': 'submitted'})
        self.message_post(body=_('Disbursement submitted to its configured approval chain.'))

    def _act_on_current_approval_step(self, action_name):
        self.ensure_one()
        step = self.approval_line_ids.filtered(lambda line: line.state == 'pending').sorted(
            key=lambda line: (line.sequence, line.id)
        )[:1]
        if not step:
            raise UserError(_('There is no pending approval step for this disbursement.'))
        return getattr(step, action_name)()

    def action_level1_approve(self):
        return self.action_approve()

    def action_level2_approve(self):
        return self.action_approve()

    def action_approve(self):
        """Approve only the current step assigned to the current user."""
        for record in self:
            record._act_on_current_approval_step('action_approve_step')

    def action_process(self):
        """Mark the approved disbursement as processed."""
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only fully approved disbursements can be processed.'))
        self.with_context(allow_disbursement_state_change=True).write({'state': 'processed'})
        self.message_post(body=_('Disbursement processed.'))

    def action_reject(self):
        """Reject only the current step assigned to the current user."""
        for record in self:
            record._act_on_current_approval_step('action_reject_step')

    def action_cancel(self):
        """Cancel disbursement."""
        self.with_context(allow_disbursement_state_change=True).write({'state': 'cancelled'})
        self.message_post(body=_('Disbursement cancelled.'))

    def action_draft(self):
        """Reset a processed disbursement to draft."""
        for rec in self:
            if rec.state == 'draft':
                continue
            rec.approval_line_ids.sudo().write({
                'state': 'pending', 'action_date': False, 'action_user_id': False,
            })
            if rec.state != 'processed':
                rec.with_context(allow_disbursement_state_change=True).write({'state': 'draft'})
                rec.message_post(body=_('Disbursement reset to draft.'))
                continue

            rec.with_context(allow_disbursement_state_change=True).write({'state': 'draft'})
            rec.message_post(body=_('Disbursement reset to draft.'))

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('amount')
    def _check_amount_positive(self):
        for disbursement in self:
            if disbursement.amount <= 0:
                raise ValidationError(_('Disbursement amount must be positive.'))
