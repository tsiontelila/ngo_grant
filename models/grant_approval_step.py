# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError, UserError


class NgoGrantApprovalStep(models.Model):
    """Configurable multi-level approval chain steps for grant workflows."""

    _name = 'ngo.grant.approval.step'
    _description = 'NGO Grant Approval Chain Step'
    _order = 'sequence, id'

    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        ondelete='cascade',
    )

    sequence = fields.Integer(
        string='Level Sequence',
        default=10,
        required=True,
    )

    name = fields.Char(
        string='Approval Step Name',
        required=True,
    )

    approver_id = fields.Many2one(
        'res.users',
        string='Assigned Approver User',
    )

    group_id = fields.Many2one(
        'res.groups',
        string='Approver Group',
    )

    min_amount = fields.Monetary(
        string='Minimum Amount Required',
        currency_field='currency_id',
        default=0.0,
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='grant_id.currency_id',
        readonly=True,
    )

    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', required=True)

    action_date = fields.Datetime(
        string='Action Date',
        readonly=True,
    )

    action_user_id = fields.Many2one(
        'res.users',
        string='Action Performed By',
        readonly=True,
    )

    notes = fields.Text(
        string='Approver Comments',
    )

    can_approve = fields.Boolean(
        compute='_compute_can_approve',
        help='Whether the current user can act on this approval step',
    )

    @api.depends('approver_id', 'group_id', 'state')
    @api.depends_context('uid')
    def _compute_can_approve(self):
        for step in self:
            step.can_approve = step._current_user_can_approve()

    def _current_user_can_approve(self):
        self.ensure_one()
        if self.state != 'pending':
            return False
        if self.env.is_admin():
            return True
        if not self.env.user.has_group('ngo_grant.group_ngo_approver'):
            return False
        return (
            self.approver_id == self.env.user
            or (not self.approver_id and self.group_id in self.env.user.all_group_ids)
        )

    def _check_approval_access(self):
        self.ensure_one()
        if not self._current_user_can_approve():
            raise AccessError(_('Only the assigned approver can act on this approval step.'))

    def _check_configuration_access(self):
        if not self.env.is_admin() and not self.env.user.has_group('ngo_grant.group_ngo_manager'):
            raise AccessError(_('Only NGO Grant Managers can configure approval steps.'))

    @api.constrains('approver_id', 'group_id')
    def _check_assignee(self):
        for step in self:
            if not step.approver_id and not step.group_id:
                raise ValidationError(_('Assign an approver user or approver group to every approval step.'))

    def action_approve_step(self):
        self.ensure_one()
        self._check_approval_access()
        self.with_context(allow_approval_step_state_change=True).write({
            'state': 'approved',
            'action_date': fields.Datetime.now(),
            'action_user_id': self.env.user.id,
        })
        self.grant_id._check_approval_chain_progress()

    def action_reject_step(self):
        self.ensure_one()
        self._check_approval_access()
        self.with_context(allow_approval_step_state_change=True).write({
            'state': 'rejected',
            'action_date': fields.Datetime.now(),
            'action_user_id': self.env.user.id,
        })
        self.grant_id.with_context(allow_workflow_state_change=True).write({'state': 'rejected'})
        self.grant_id.message_post(body=_("Grant approval rejected at step: %s") % self.name)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_configuration_access()
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals and not self.env.context.get('allow_approval_step_state_change'):
            raise AccessError(_('Approval status is set only by the approval actions.'))
        configuration_fields = {'approver_id', 'group_id', 'sequence', 'name', 'min_amount'}
        if configuration_fields.intersection(vals):
            self._check_configuration_access()
        return super().write(vals)
