# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class NgoGrantBudgetPeriod(models.Model):
    """Multi-year fiscal periods and yearly sub-budgets for grants."""

    _name = 'ngo.grant.budget.period'
    _description = 'NGO Grant Multi-Year Fiscal Budget Period'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date, id'

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
        string='Period Name (e.g. Year 1, FY2025)',
        required=True,
        default=lambda self: _('FY Sub-Budget'),
        tracking=True,
    )

    sequence = fields.Integer(
        string='Fiscal Year Number',
        default=1,
    )

    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    end_date = fields.Date(
        string='End Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    allocated_amount = fields.Monetary(
        string='Sub-Budget Allocated Amount',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
    )


    warning_threshold = fields.Float(
        string='Warning Threshold (%)',
        default=80.0,
        help='Percentage at which soft warning is triggered.',
    )

    soft_stop_threshold = fields.Float(
        string='Soft-Stop Threshold (%)',
        default=95.0,
        help='Percentage at which soft-stop warning is triggered.',
    )

    hard_stop_threshold = fields.Float(
        string='Hard-Stop Threshold (%)',
        default=100.0,
        help='Percentage at which strict validation error blocks expense.',
    )

    overrun_action = fields.Selection([
        ('allow', 'Allow (Log Warning)'),
        ('soft_stop', 'Soft-Stop (Requires Manager Approval)'),
        ('hard_stop', 'Hard-Stop (Block Transactions)'),
    ],
        string='Overrun Rule',
        default='soft_stop',
        required=True,
        tracking=True,
        help='Action to take when this budget period exceeds its thresholds.',
    )

    spent_amount = fields.Monetary(
        string='Actual Spent Amount',
        currency_field='currency_id',
        compute='_compute_spent_amount',
        store=True,
        help='Actual expenditure tracking is not configured.',
    )

    committed_amount = fields.Monetary(
        string='Committed Amount',
        currency_field='currency_id',
        compute='_compute_spent_amount',
        store=True,
    )

    remaining_amount = fields.Monetary(
        string='Remaining Budget',
        currency_field='currency_id',
        compute='_compute_remaining_amount',
        store=True,
    )

    utilization_rate = fields.Float(
        string='Utilization (%)',
        compute='_compute_remaining_amount',
        store=True,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', required=True, tracking=True)

    @api.depends('start_date', 'end_date')
    def _compute_spent_amount(self):
        for record in self:
            record.spent_amount = 0.0
            record.committed_amount = 0.0

    @api.depends('allocated_amount', 'spent_amount')
    def _compute_remaining_amount(self):
        for record in self:
            allocated = record.allocated_amount or 0.0
            spent = record.spent_amount or 0.0
            record.remaining_amount = allocated - spent
            if allocated > 0:
                record.utilization_rate = (spent / allocated) * 100.0
            else:
                record.utilization_rate = 0.0


    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_(
                    "Budget Period Start Date (%s) cannot be after End Date (%s) for period '%s'. "
                    "Please ensure the full year (e.g. 2026) is included in both dates."
                ) % (record.start_date, record.end_date, record.name or ''))

    @api.onchange('grant_id', 'sequence')
    def _onchange_grant_defaults(self):
        """Auto-populate start/end dates based on grant start_date and period year sequence."""
        if self.grant_id and self.grant_id.start_date:
            try:
                dt = fields.Date.to_date(self.grant_id.start_date)
                if dt:
                    seq = self.sequence or 1
                    year_offset = max(0, seq - 1)
                    target_year = dt.year + year_offset
                    self.start_date = dt.replace(year=target_year, month=1, day=1)
                    self.end_date = dt.replace(year=target_year, month=12, day=31)
                    if not self.name or self.name in [_('FY Sub-Budget'), 'FY Sub-Budget']:
                        self.name = _("Year %d (FY%d)") % (seq, target_year)
            except Exception:
                pass






    @api.model
    def check_budget_overruns(self):
        """Cron: Scan all active budget periods and send notifications on threshold breaches."""
        active_periods = self.search([('state', '=', 'active')])
        for period in active_periods:
            rate = period.utilization_rate
            grant = period.grant_id

            if rate >= period.hard_stop_threshold:
                level = 'hard_stop'
                subject = _("[HARD-STOP] Budget Hard-Stop: %s / %s") % (grant.grant_number, period.name)
                body = _(
                    "⛔ HARD-STOP: Budget period <b>%s</b> on grant <b>%s</b> has reached "
                    "<b>%.1f%%</b> utilization (Hard-Stop threshold: %.1f%%). "
                    "All new transactions are blocked until resolved."
                ) % (period.name, grant.grant_number, rate, period.hard_stop_threshold)
            elif rate >= period.soft_stop_threshold:
                level = 'soft_stop'
                subject = _("[SOFT-STOP] Budget Soft-Stop: %s / %s") % (grant.grant_number, period.name)
                body = _(
                    "🔶 SOFT-STOP: Budget period <b>%s</b> on grant <b>%s</b> has reached "
                    "<b>%.1f%%</b> utilization (Soft-Stop threshold: %.1f%%). "
                    "Manager approval is required for additional expenditures."
                ) % (period.name, grant.grant_number, rate, period.soft_stop_threshold)
            elif rate >= period.warning_threshold:
                level = 'warning'
                subject = _("[WARNING] Budget Warning: %s / %s") % (grant.grant_number, period.name)
                body = _(
                    "⚠️ WARNING: Budget period <b>%s</b> on grant <b>%s</b> has reached "
                    "<b>%.1f%%</b> utilization (Warning threshold: %.1f%%). "
                    "Please review remaining budget allocation."
                ) % (period.name, grant.grant_number, rate, period.warning_threshold)
            else:
                continue  # No threshold breached

            # Post chatter message on grant
            grant.message_post(
                body=body,
                subject=subject,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

            # Send email notification via budget overrun template if it exists
            template = self.env.ref('ngo_grant.email_template_budget_overrun', raise_if_not_found=False)
            if template and grant.user_id:
                template.with_context(
                    budget_period=period,
                    overrun_level=level,
                    overrun_body=body,
                ).send_mail(period.id, force_send=True, raise_exception=False)

