from odoo import _, api, fields, models
from odoo.exceptions import AccessError


def check_cancellation_access(records):
    """Allow cancellation only to system and NGO Grant Administrators."""
    user = records.env.user
    if not (
        records.env.is_admin()
        or records.env.su
        or user.has_group('base.group_system')
        or user.has_group('ngo_grant.group_ngo_director')
    ):
        raise AccessError(_('Only system administrators and NGO Grant Administrators can cancel records.'))


def user_can_reset_record(record):
    user = record.env.user
    if record.env.is_admin() or record.env.su or user.has_group('base.group_system') or user.has_group('ngo_grant.group_ngo_director'):
        return True
    if record.create_uid == user:
        return True
    for field_name in ('responsible_id', 'responsible_user_id', 'user_id', 'owner_id', 'assigned_to'):
        if field_name in record._fields:
            assigned = record[field_name]
            if assigned and assigned == user:
                return True
    if 'responsible_employee_id' in record._fields:
        employee = record.responsible_employee_id
        if employee and employee.user_id == user:
            return True
    if 'approval_line_ids' in record._fields and user in record.approval_line_ids.mapped('approver_id'):
        return True
    return False


def check_reset_access(records):
    if any(not user_can_reset_record(record) for record in records):
        raise AccessError(_('Only the responsible user, record creator, or an administrator can reset a cancelled record to Draft.'))


class NgoCancellationAccessMixin(models.AbstractModel):
    _name = 'ngo.cancellation.access.mixin'
    _description = 'NGO Grant Cancellation and Reset Access Guard'

    can_reset_cancelled = fields.Boolean(compute='_compute_can_reset_cancelled')

    @api.depends_context('uid')
    def _compute_can_reset_cancelled(self):
        for record in self:
            record.can_reset_cancelled = user_can_reset_record(record)

    def write(self, vals):
        if not self.env.su:
            is_cancel = vals.get('state') == 'cancelled'
            is_reset = vals.get('state') == 'draft' and any(record.state == 'cancelled' for record in self)
            if is_cancel:
                check_cancellation_access(self)
            elif is_reset:
                check_reset_access(self)
        return super().write(vals)
