# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError
from .workflow_access import check_cancellation_access, check_reset_access


class NgoSubgrantAmendment(models.Model):
    _name = 'ngo.subgrant.amendment'
    _description = 'Subgrant Amendment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ngo.cancellation.access.mixin']
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
    effective_date = fields.Date(tracking=True)
    amount_change = fields.Monetary(currency_field='currency_id', tracking=True)
    previous_approved_amount = fields.Monetary(string='Previous Approved Amount', currency_field='currency_id', readonly=True, store=True, tracking=True)
    new_approved_amount = fields.Monetary(string='New Approved Amount', currency_field='currency_id', compute='_compute_new_approved_amount', store=True, tracking=True)
    original_end_date = fields.Date(required=True, tracking=True)
    new_end_date = fields.Date(tracking=True)
    description = fields.Text(required=True, tracking=True)
    amendment_reason = fields.Text(tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='draft', required=True, tracking=True)
    approved_by = fields.Many2one('res.users', readonly=True, tracking=True)
    approval_date = fields.Date(readonly=True, tracking=True)

    @api.depends('previous_approved_amount', 'amount_change')
    def _compute_new_approved_amount(self):
        for rec in self:
            rec.new_approved_amount = rec.previous_approved_amount + (rec.amount_change or 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('amendment_number', _('New')) == _('New'):
                vals['amendment_number'] = self.env['ir.sequence'].next_by_code('ngo.subgrant.amendment') or _('New')
            if vals.get('subgrant_id'):
                vals['previous_approved_amount'] = self.env['ngo.subgrant'].browse(vals['subgrant_id']).approved_amount
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
            vals = {
                'approved_amount': rec.new_approved_amount,
                'allocation_amount': rec.new_approved_amount,
            }
            if rec.new_end_date:
                vals['end_date'] = rec.new_end_date
            rec.subgrant_id.sudo().write(vals)
            rec.write({'state': 'approved', 'approved_by': self.env.user.id, 'approval_date': fields.Date.today()})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_cancel(self):
        check_cancellation_access(self)
        for amendment in self:
            if amendment.state == 'approved' and (amendment.amount_change or amendment.new_end_date):
                vals = {}
                if amendment.amount_change:
                    vals.update({
                        'approved_amount': amendment.previous_approved_amount,
                        'allocation_amount': amendment.previous_approved_amount,
                    })
                if amendment.new_end_date:
                    vals['end_date'] = amendment.original_end_date
                if vals:
                    amendment.subgrant_id.sudo().write(vals)
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({'state': 'cancelled'})
        self.sudo().message_post(body=_('Subgrant amendment cancelled.'))

    def action_reset_cancelled(self):
        check_reset_access(self)
        if any(record.state != 'cancelled' for record in self):
            raise ValidationError(_('Only cancelled subgrant amendments can be reset to Draft.'))
        for amendment in self:
            amendment.sudo().with_context(allow_cancel_reset_state_change=True, reset_amendment_snapshot=True).write({
                'state': 'draft', 'approved_by': False, 'approval_date': False,
                'previous_approved_amount': amendment.subgrant_id.approved_amount,
                'original_end_date': amendment.subgrant_id.end_date,
            })
        self.sudo().message_post(body=_('Cancelled subgrant amendment reset to Draft for revision.'))

    def write(self, vals):
        if 'previous_approved_amount' in vals and not (self.env.su and self.env.context.get('reset_amendment_snapshot')):
            raise ValidationError(_('Previous Approved Amount is a fixed snapshot and cannot be changed.'))
        if not self.env.su:
            for amendment in self:
                if amendment.state in ('approved', 'cancelled') and set(vals) - {'state'}:
                    raise AccessError(_('Approved subgrant amendments are locked. Cancel them before resetting and editing.'))
                if amendment.state in ('approved', 'cancelled') and vals.get('state') == 'draft':
                    raise AccessError(_('An approved subgrant amendment must be cancelled before it can be reset to Draft.'))
        return super().write(vals)


class NgoSubgrantDisbursement(models.Model):
    _name = 'ngo.subgrant.disbursement'
    _description = 'Subgrant Disbursement'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ngo.cancellation.access.mixin']
    _order = 'disbursement_date desc, id desc'

    name = fields.Char(string='Disbursement Reference', required=True, copy=False, default=lambda self: _('New'), tracking=True)
    subgrant_id = fields.Many2one('ngo.subgrant', string='Subgrant', required=True, ondelete='cascade', tracking=True)
    currency_id = fields.Many2one(related='subgrant_id.currency_id', store=True, readonly=True)
    amount = fields.Monetary(string='Disbursement Amount', currency_field='currency_id', required=True, tracking=True)
    disbursement_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    disbursement_type = fields.Char(string='Legacy Disbursement Type Code', readonly=True, copy=False)
    disbursement_type_id = fields.Many2one(
        'ngo.grant.disbursement.type', string='Disbursement Type', tracking=True,
        ondelete='restrict', compute='_compute_disbursement_type_id',
        inverse='_inverse_disbursement_type_id', store=True,
    )
    approval_line_ids = fields.One2many(
        'ngo.subgrant.disbursement.approval.step', 'disbursement_id',
        string='Approval Chain', copy=False,
    )
    payment_reference = fields.Char(tracking=True)
    description = fields.Text(tracking=True)
    notes = fields.Text(string='Internal Notes', tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    rejection_reason = fields.Text(tracking=True)
    level1_approver_id = fields.Many2one('res.users', string='Level 1 Approver', tracking=True)
    level1_approved_by = fields.Many2one('res.users', string='L1 Approved By', readonly=True)
    level1_approved_date = fields.Datetime(string='L1 Approval Date', readonly=True)
    level1_notes = fields.Text(string='Level 1 Notes')
    level2_approver_id = fields.Many2one('res.users', string='Level 2 Approver', tracking=True)
    level2_approved_by = fields.Many2one('res.users', string='L2 Approved By', readonly=True)
    level2_approved_date = fields.Datetime(string='L2 Approval Date', readonly=True)
    level2_notes = fields.Text(string='Level 2 Notes')
    state = fields.Selection([
        ('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'),
        ('processed', 'Processed'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    approved_by = fields.Many2one('res.users', readonly=True)
    approval_date = fields.Date(readonly=True)

    def _is_ngo_approver(self, user):
        approver_group = self.env.ref('ngo_grant.group_ngo_approver', raise_if_not_found=False)
        return bool(user and approver_group and approver_group in user.all_group_ids)

    @api.constrains('level1_approver_id', 'level2_approver_id')
    def _check_assigned_approvers(self):
        for record in self:
            for approver in (record.level1_approver_id, record.level2_approver_id):
                if approver and not record._is_ngo_approver(approver):
                    raise ValidationError(_('Level 1 and Level 2 approvers must have the NGO Grant Approver role.'))

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

    @api.model_create_multi
    def create(self, vals_list):
        prepared_values = []
        approval_templates = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get('state') and vals['state'] != 'draft':
                raise AccessError(_('New subgrant disbursements must start in Draft.'))
            vals.pop('approval_line_ids', None)
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ngo.subgrant.disbursement') or _('New')
            if not vals.get('disbursement_type_id'):
                legacy_code = vals.get('disbursement_type') or 'installment'
                disbursement_type = self.env['ngo.grant.disbursement.type'].search([('code', '=', legacy_code)], limit=1)
                vals['disbursement_type_id'] = disbursement_type.id or False
            if vals.get('disbursement_type_id'):
                disbursement_type = self.env['ngo.grant.disbursement.type'].browse(vals['disbursement_type_id'])
                vals['disbursement_type'] = disbursement_type.code
                templates = disbursement_type.approval_step_ids.sorted(key=lambda item: (item.sequence, item.id))
            else:
                templates = self.env['ngo.grant.disbursement.type.approval.step']
            approval_templates.append(templates)
            prepared_values.append(vals)
        records = super().create(prepared_values)
        Step = self.env['ngo.subgrant.disbursement.approval.step'].sudo().with_context(subgrant_disbursement_approval_setup=True)
        for record, templates in zip(records, approval_templates):
            Step.create([{
                'disbursement_id': record.id,
                'sequence': template.sequence,
                'name': template.name,
                'approver_id': template.approver_id.id,
                'group_id': template.group_id.id,
            } for template in templates])
        return records

    def write(self, vals):
        vals = dict(vals)
        if 'state' in vals and not self.env.context.get('allow_subgrant_disbursement_state_change'):
            raise AccessError(_('Subgrant disbursement state can only be changed through its workflow actions.'))
        if not self.env.su and vals.get('state') == 'draft' and any(record.state in ('approved', 'processed') for record in self):
            raise AccessError(_('Cancel the approved subgrant disbursement before resetting it to Draft.'))
        if not self.env.su and set(vals) - {'state'}:
            if any(record.state in ('approved', 'processed', 'cancelled') for record in self):
                raise AccessError(_('Approved subgrant disbursements are locked. An administrator must cancel them before they can be reset and edited.'))
        vals.pop('approval_line_ids', None)
        changing_type = 'disbursement_type_id' in vals
        if changing_type and any(record.state != 'draft' for record in self):
            raise UserError(_('The disbursement type can only be changed while the subgrant disbursement is in Draft.'))
        if changing_type:
            selected_type = self.env['ngo.grant.disbursement.type'].browse(vals['disbursement_type_id'])
            vals['disbursement_type'] = selected_type.code or False
        result = super().write(vals)
        if changing_type:
            Step = self.env['ngo.subgrant.disbursement.approval.step'].sudo().with_context(subgrant_disbursement_approval_setup=True)
            for record in self:
                record.approval_line_ids.sudo().unlink()
                templates = record.disbursement_type_id.approval_step_ids.sorted(key=lambda item: (item.sequence, item.id))
                Step.create([{
                    'disbursement_id': record.id,
                    'sequence': template.sequence,
                    'name': template.name,
                    'approver_id': template.approver_id.id,
                    'group_id': template.group_id.id,
                } for template in templates])
        return result

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
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only Draft subgrant disbursements can be submitted.'))
            # Draft forms can display onchange-created approval steps that were
            # not persisted when the disbursement was first saved. Rebuild the
            # steps from the selected type before validating the workflow.
            if not record.approval_line_ids.sudo().exists():
                templates = record.disbursement_type_id.sudo().approval_step_ids.sorted(
                    key=lambda item: (item.sequence, item.id)
                )
                if templates:
                    Step = self.env['ngo.subgrant.disbursement.approval.step'].sudo().with_context(
                        subgrant_disbursement_approval_setup=True
                    )
                    Step.create([{
                        'disbursement_id': record.id,
                        'sequence': template.sequence,
                        'name': template.name,
                        'approver_id': template.approver_id.id,
                        'group_id': template.group_id.id,
                    } for template in templates])
            if not record.approval_line_ids.sudo().exists():
                raise UserError(_('The selected disbursement type has no saved approval steps. Configure its approvers and save the type before submitting.'))
        self.with_context(allow_subgrant_disbursement_state_change=True).write({'state': 'submitted'})
        self.message_post(body=_('Subgrant disbursement submitted to its configured approval chain.'))

    def action_approve(self):
        for record in self:
            record._act_on_current_approval_step('action_approve_step')

    def _act_on_current_approval_step(self, action_name):
        self.ensure_one()
        step = self.approval_line_ids.filtered(lambda line: line.state == 'pending').sorted(
            key=lambda line: (line.sequence, line.id)
        )[:1]
        if not step:
            raise UserError(_('There is no pending approval step for this subgrant disbursement.'))
        return getattr(step, action_name)()

    def action_process(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only approved subgrant disbursements can be processed.'))
            rec.with_context(allow_subgrant_disbursement_state_change=True).write({'state': 'processed'})
        self.message_post(body=_('Subgrant disbursement processed.'))

    def action_reject(self):
        for record in self:
            record._act_on_current_approval_step('action_reject_step')

    def action_cancel(self):
        check_cancellation_access(self)
        self.sudo().with_context(allow_subgrant_disbursement_state_change=True, allow_cancel_reset_state_change=True).write({'state': 'cancelled'})
        self.sudo().message_post(body=_('Subgrant disbursement cancelled.'))

    def action_reset_cancelled(self):
        check_reset_access(self)
        for record in self:
            if record.state != 'cancelled':
                raise ValidationError(_('Only cancelled subgrant disbursements can be reset to Draft.'))
            record.approval_line_ids.sudo().with_context(allow_subgrant_disbursement_approval_action=True).write({
                'state': 'pending', 'action_date': False, 'action_user_id': False,
            })
            record.sudo().with_context(allow_subgrant_disbursement_state_change=True, allow_cancel_reset_state_change=True).write({
                'state': 'draft', 'approved_by': False, 'approval_date': False, 'rejection_reason': False,
            })
            record.sudo().message_post(body=_('Cancelled subgrant disbursement reset to Draft for revision.'))

    def action_draft(self):
        """Reset only a cancelled disbursement, with responsible-user access."""
        return self.action_reset_cancelled()


class NgoSubgrantDisbursementApprovalStep(models.Model):
    _name = 'ngo.subgrant.disbursement.approval.step'
    _description = 'Subgrant Disbursement Approval Step'
    _order = 'sequence, id'

    disbursement_id = fields.Many2one('ngo.subgrant.disbursement', required=True, ondelete='cascade')
    sequence = fields.Integer(required=True)
    name = fields.Char(required=True)
    approver_id = fields.Many2one('res.users', string='Assigned Approver User')
    group_id = fields.Many2one('res.groups', string='Approver Group')
    state = fields.Selection([('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', required=True)
    action_date = fields.Datetime(readonly=True)
    action_user_id = fields.Many2one('res.users', string='Action Performed By', readonly=True)
    can_approve = fields.Boolean(compute='_compute_can_approve')

    @api.depends('approver_id', 'group_id', 'state', 'sequence', 'disbursement_id.state', 'disbursement_id.approval_line_ids.state')
    @api.depends_context('uid')
    def _compute_can_approve(self):
        for step in self:
            step.can_approve = step._current_user_can_approve()

    def _current_user_can_approve(self):
        self.ensure_one()
        disbursement = self.disbursement_id
        if self.state != 'pending' or disbursement.state != 'submitted':
            return False
        pending = disbursement.approval_line_ids.filtered(lambda line: line.state == 'pending').sorted(
            key=lambda line: (line.sequence, line.id)
        )
        user = self.env.user
        return bool(pending and pending[0] == self and (
            (self.approver_id and self.approver_id == user)
            or (self.group_id and self.group_id in user.all_group_ids)
        ))

    def _check_approval_access(self):
        self.ensure_one()
        if not self._current_user_can_approve():
            raise ValidationError(_('Only the assigned approver for the current subgrant disbursement step can act on it.'))

    def action_approve_step(self):
        self.ensure_one()
        self._check_approval_access()
        self.sudo().with_context(allow_subgrant_disbursement_approval_action=True).write({
            'state': 'approved', 'action_date': fields.Datetime.now(), 'action_user_id': self.env.user.id,
        })
        disbursement = self.disbursement_id
        if not disbursement.approval_line_ids.filtered(lambda line: line.state == 'pending'):
            disbursement.sudo().with_context(allow_subgrant_disbursement_state_change=True).write({
                'state': 'approved', 'approved_by': self.env.user.id, 'approval_date': fields.Date.today(),
            })
            disbursement.sudo().message_post(body=_('All configured approval steps are complete. Subgrant disbursement approved.'))
        else:
            disbursement.sudo().message_post(body=_('Approval step completed: %s') % self.name)

    def action_reject_step(self):
        self.ensure_one()
        self._check_approval_access()
        self.sudo().with_context(allow_subgrant_disbursement_approval_action=True).write({
            'state': 'rejected', 'action_date': fields.Datetime.now(), 'action_user_id': self.env.user.id,
        })
        self.disbursement_id.sudo().with_context(allow_subgrant_disbursement_state_change=True).write({'state': 'rejected'})
        self.disbursement_id.sudo().message_post(body=_('Subgrant disbursement rejected at approval step: %s') % self.name)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.is_admin() and not self.env.context.get('subgrant_disbursement_approval_setup'):
            raise ValidationError(_('Approval steps are created from the disbursement type configuration.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.is_admin() and not self.env.context.get('allow_subgrant_disbursement_approval_action'):
            raise ValidationError(_('Approval steps can only be changed through their approval actions.'))
        return super().write(vals)


class NgoSubgrantDocument(models.Model):
    _name = 'ngo.subgrant.document'
    _description = 'Subgrant Document'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ngo.cancellation.access.mixin']
    _order = 'document_date desc, id desc'

    name = fields.Char(string='Document Name', required=True, tracking=True)
    subgrant_id = fields.Many2one('ngo.subgrant', string='Subgrant', required=True, ondelete='cascade', tracking=True)
    compliance_id = fields.Many2one('ngo.grant.compliance', string='Compliance Item', ondelete='cascade', tracking=True)
    document_type = fields.Selection([
        ('agreement', 'Subgrant Agreement'), ('amendment', 'Amendment'),
        ('donor_approval', 'Donor Approval'), ('financial_report', 'Financial Report'),
        ('compliance', 'Compliance'), ('other', 'Other'),
    ], default='other', required=True, tracking=True)
    document_date = fields.Date(default=fields.Date.context_today, tracking=True)
    file = fields.Binary(string='File', attachment=True)
    file_name = fields.Char(string='File Name', tracking=True)
    description = fields.Text(tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'),
        ('active', 'Active'), ('archived', 'Archived'), ('rejected', 'Rejected'),
        ('expired', 'Expired'), ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    approved = fields.Boolean(default=False, readonly=True, tracking=True)
    approved_by = fields.Many2one('res.users', readonly=True, tracking=True)
    approval_date = fields.Date(readonly=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state') and vals['state'] != 'draft':
                raise AccessError(_('New subgrant documents must start in Draft.'))
            if vals.get('approved') or vals.get('approved_by') or vals.get('approval_date'):
                raise AccessError(_('Subgrant document approval is set automatically by its approval action.'))
            compliance_id = vals.get('compliance_id') or self.env.context.get('default_compliance_id')
            if compliance_id and not vals.get('subgrant_id'):
                vals['subgrant_id'] = self.env['ngo.grant.compliance'].browse(compliance_id).subgrant_id.id
        return super().create(vals_list)

    @api.constrains('subgrant_id', 'compliance_id')
    def _check_compliance_subgrant(self):
        for document in self:
            if document.compliance_id and document.compliance_id.subgrant_id != document.subgrant_id:
                raise ValidationError(_('A compliance evidence document must belong to the same subgrant as its compliance item.'))

    def action_cancel(self):
        check_cancellation_access(self)
        self.sudo().with_context(allow_subgrant_document_workflow_change=True).write({'state': 'cancelled'})
        self.sudo().message_post(body=_('Subgrant document cancelled.'))

    def action_submit(self):
        self._check_manager_access()
        if any(document.state != 'draft' for document in self):
            raise UserError(_('Only Draft subgrant documents can be submitted.'))
        self.with_context(allow_subgrant_document_workflow_change=True).write({'state': 'submitted'})
        self.message_post(body=_('Subgrant document submitted for approval.'))

    def action_approve(self):
        self._check_manager_access()
        if any(document.state != 'submitted' for document in self):
            raise UserError(_('Only submitted subgrant documents can be approved.'))
        self.sudo().with_context(allow_subgrant_document_workflow_change=True).write({
            'state': 'approved', 'approved': True,
            'approved_by': self.env.user.id, 'approval_date': fields.Date.today(),
        })
        self.message_post(body=_('Subgrant document approved.'))

    def action_reject(self):
        self._check_manager_access()
        if any(document.state != 'submitted' for document in self):
            raise UserError(_('Only submitted subgrant documents can be rejected.'))
        self.with_context(allow_subgrant_document_workflow_change=True).write({'state': 'rejected'})
        self.message_post(body=_('Subgrant document rejected.'))

    def _check_manager_access(self):
        if not self.env.is_admin() and not self.env.user.has_group('ngo_grant.group_ngo_manager'):
            raise AccessError(_('Only NGO Grant Managers can perform this action.'))

    def action_reset_cancelled(self):
        check_reset_access(self)
        if any(document.state != 'cancelled' for document in self):
            raise ValidationError(_('Only cancelled subgrant documents can be reset to Draft.'))
        self.sudo().with_context(allow_subgrant_document_workflow_change=True).write({'state': 'draft', 'approved': False, 'approved_by': False, 'approval_date': False})
        self.sudo().message_post(body=_('Cancelled subgrant document reset to Draft for revision.'))

    def write(self, vals):
        protected_fields = {'state', 'approved', 'approved_by', 'approval_date'}
        if protected_fields.intersection(vals) and not self.env.context.get('allow_subgrant_document_workflow_change'):
            raise AccessError(_('Subgrant document status can only be changed through its workflow actions.'))
        locked_states = ('approved', 'active', 'archived', 'expired', 'cancelled')
        if not self.env.su and any(document.state in locked_states for document in self):
            if 'state' in vals and vals['state'] != 'cancelled':
                raise AccessError(_('Approved subgrant documents cannot be changed until an administrator cancels them.'))
            if set(vals) - {'state'}:
                raise AccessError(_('Approved subgrant documents are locked. An administrator must cancel the document before it can be reset and edited.'))
        return super().write(vals)
