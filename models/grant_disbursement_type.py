# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class NgoGrantDisbursementType(models.Model):
    _name = 'ngo.grant.disbursement.type'
    _description = 'NGO Grant Disbursement Type'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, copy=False, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    approval_step_ids = fields.One2many(
        'ngo.grant.disbursement.type.approval.step', 'type_id',
        string='Approval Chain', copy=True,
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Disbursement type code must be unique.'),
    ]

    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if not record.code or not record.code.strip():
                raise ValidationError(_('A disbursement type code is required.'))


class NgoGrantDisbursementTypeApprovalStep(models.Model):
    _name = 'ngo.grant.disbursement.type.approval.step'
    _description = 'NGO Grant Disbursement Type Approval Step'
    _order = 'sequence, id'

    type_id = fields.Many2one(
        'ngo.grant.disbursement.type', string='Disbursement Type',
        required=True, ondelete='cascade',
    )
    sequence = fields.Integer(default=10, required=True)
    name = fields.Char(string='Approval Step Name', required=True)
    approver_id = fields.Many2one('res.users', string='Assigned Approver User')
    group_id = fields.Many2one('res.groups', string='Approver Group')

    @api.constrains('approver_id', 'group_id')
    def _check_assignee(self):
        for step in self:
            if not step.approver_id and not step.group_id:
                raise ValidationError(_('Assign an approver user or approver group to every approval step.'))


class NgoGrantDisbursementApprovalStep(models.Model):
    _name = 'ngo.grant.disbursement.approval.step'
    _description = 'NGO Grant Disbursement Approval Step'
    _order = 'sequence, id'

    disbursement_id = fields.Many2one(
        'ngo.grant.disbursement', required=True, ondelete='cascade',
    )
    sequence = fields.Integer(required=True)
    name = fields.Char(required=True)
    approver_id = fields.Many2one('res.users', string='Assigned Approver User')
    group_id = fields.Many2one('res.groups', string='Approver Group')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', required=True)
    action_date = fields.Datetime(readonly=True)
    action_user_id = fields.Many2one('res.users', string='Action Performed By', readonly=True)
    can_approve = fields.Boolean(compute='_compute_can_approve')

    @api.depends('approver_id', 'group_id', 'state', 'sequence', 'disbursement_id.state',
                 'disbursement_id.approval_line_ids.state')
    @api.depends_context('uid')
    def _compute_can_approve(self):
        for step in self:
            step.can_approve = step._current_user_can_approve()

    def _current_user_can_approve(self):
        self.ensure_one()
        disbursement = self.disbursement_id
        if self.state != 'pending' or disbursement.state not in ('submitted', 'level1_approved'):
            return False
        pending_steps = disbursement.approval_line_ids.filtered(
            lambda line: line.state == 'pending'
        ).sorted(key=lambda line: (line.sequence, line.id))
        if not pending_steps or pending_steps[0] != self:
            return False
        user = self.env.user
        return bool(
            (self.approver_id and self.approver_id == user)
            or (self.group_id and self.group_id in user.all_group_ids)
        )

    def _check_approval_access(self):
        self.ensure_one()
        if not self._current_user_can_approve():
            raise ValidationError(_('Only the assigned approver for the current step can act on it.'))

    def action_approve_step(self):
        self.ensure_one()
        self._check_approval_access()
        self.sudo().with_context(allow_disbursement_approval_action=True).write({
            'state': 'approved',
            'action_date': fields.Datetime.now(),
            'action_user_id': self.env.user.id,
        })
        disbursement = self.disbursement_id
        if not disbursement.approval_line_ids.filtered(lambda line: line.state == 'pending'):
            disbursement.sudo().with_context(allow_disbursement_state_change=True).write({'state': 'approved'})
            disbursement.sudo().message_post(body=_('All configured approval steps are complete. Disbursement approved.'))
        else:
            disbursement.sudo().message_post(body=_('Approval step completed: %s') % self.name)

    def action_reject_step(self):
        self.ensure_one()
        self._check_approval_access()
        self.sudo().with_context(allow_disbursement_approval_action=True).write({
            'state': 'rejected',
            'action_date': fields.Datetime.now(),
            'action_user_id': self.env.user.id,
        })
        disbursement = self.disbursement_id
        disbursement.sudo().with_context(allow_disbursement_state_change=True).write({'state': 'rejected'})
        disbursement.sudo().message_post(body=_('Disbursement rejected at approval step: %s') % self.name)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.is_admin() and not self.env.context.get('disbursement_approval_setup'):
            raise ValidationError(_('Approval steps are created from the disbursement type configuration.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.is_admin() and not self.env.context.get('allow_disbursement_approval_action'):
            raise ValidationError(_('Approval steps can only be changed through their approval actions.'))
        return super().write(vals)
