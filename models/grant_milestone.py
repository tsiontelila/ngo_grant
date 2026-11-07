# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from .workflow_access import check_cancellation_access, check_reset_access


class NgoGrantMilestone(models.Model):
    """Conditions and milestones linked to grant fund releases."""

    _name = 'ngo.grant.milestone'
    _description = 'NGO Grant Milestone & Release Condition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ngo.cancellation.access.mixin']
    _order = 'target_date, id'

    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='grant_id.currency_id',
        readonly=True,
    )

    name = fields.Char(
        string='Milestone / Condition Name',
        required=True,
        tracking=True,
    )
    
    description = fields.Text(
        string='Description',
    )
    
    target_date = fields.Date(
        string='Target Date',
        required=True,
        tracking=True,
    )
    
    completion_date = fields.Date(
        string='Completion Date',
        tracking=True,
    )
    
    release_amount = fields.Monetary(
        string='Release Amount',
        currency_field='currency_id',
        tracking=True,
        help='Fund amount tied to achieving this milestone condition',
    )
    
    state = fields.Selection([
        ('draft', 'Pending'),
        ('submitted', 'Submitted for Review'),
        ('verified', 'Verified / Met'),
        ('released', 'Funds Released'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)

    disbursement_id = fields.Many2one(
        'ngo.grant.disbursement',
        string='Linked Disbursement',
        readonly=True,
        help='Disbursement generated upon achieving this milestone',
    )

    def action_cancel(self):
        check_cancellation_access(self)
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({'state': 'cancelled'})
        for milestone in self:
            milestone.grant_id.sudo().message_post(body=_('Milestone %s cancelled.') % milestone.name)

    def action_reset_cancelled(self):
        check_reset_access(self)
        if any(milestone.state != 'cancelled' for milestone in self):
            raise UserError(_('Only cancelled milestones can be reset to Draft.'))
        self.sudo().with_context(allow_cancel_reset_state_change=True).write({'state': 'draft', 'completion_date': False})
        for milestone in self:
            milestone.grant_id.sudo().message_post(body=_('Cancelled milestone %s reset to Draft for revision.') % milestone.name)

    def action_submit(self):
        self.write({'state': 'submitted'})
        self.grant_id.message_post(body=_("Milestone %s submitted for verification.") % self.name)

    def action_verify(self):
        self.write({
            'state': 'verified',
            'completion_date': fields.Date.today(),
        })
        self.grant_id.message_post(body=_("Milestone %s verified as completed.") % self.name)

    def action_release_funds(self):
        self.ensure_one()
        if self.state != 'verified':
            raise UserError(_("Milestone must be verified before releasing funds."))
        if self.release_amount <= 0:
            raise UserError(_("Release amount must be positive."))
            
        disbursement_vals = {
            'grant_id': self.grant_id.id,
            'amount': self.release_amount,
            'disbursement_date': fields.Date.today(),
            'disbursement_type_id': self.env['ngo.grant.disbursement.type'].search(
                [('code', '=', 'installment')], limit=1,
            ).id,
            'description': _("Milestone Release: %s") % self.name,
            'state': 'draft',
        }
        disbursement = self.env['ngo.grant.disbursement'].create(disbursement_vals)
        self.write({
            'state': 'released',
            'disbursement_id': disbursement.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Grant Disbursement'),
            'res_model': 'ngo.grant.disbursement',
            'res_id': disbursement.id,
            'view_mode': 'form',
        }
