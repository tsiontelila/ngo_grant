# -*- coding: utf-8 -*-

import json
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.tools.safe_eval import safe_eval


class NgoGrantDashboard(models.Model):
    _name = "ngo.grant.dashboard"
    _description = "NGO Grant Dashboard"
    _order = "sequence, id"

    name = fields.Char(
        string="Name",
        required=True,
    )

    description = fields.Char(
        string="Description",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )

    model_name = fields.Char(
        string="Model",
        required=True,
    )

    action_xmlid = fields.Char(
        string="Action XML ID",
        required=True,
    )

    groupby_field = fields.Char(
        string="Group By Field",
        required=True,
    )

    chart_type = fields.Selection(
        [
            ("pie", "Pie"),
            ("donut", "Donut"),
            ("horizontal_bar", "Horizontal Bar"),
            ("vertical_bar", "Vertical Bar"),
            ("status", "Status"),
        ],
        string="Chart Type",
        default="status",
        required=True,
    )

    color = fields.Char(
        string="Color",
        default="#714B67",
    )

    icon = fields.Char(
        string="Icon",
        default="fa fa-bar-chart",
    )

    chart_style = fields.Char(
        string="Chart Style",
    )

    total_count = fields.Integer(
        string="Total",
        compute="_compute_dashboard_data",
    )

    status_1_label = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_1_value = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_1_count = fields.Integer(
        compute="_compute_dashboard_data",
    )
    status_1_percent = fields.Float(
        compute="_compute_dashboard_data",
    )

    status_2_label = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_2_value = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_2_count = fields.Integer(
        compute="_compute_dashboard_data",
    )
    status_2_percent = fields.Float(
        compute="_compute_dashboard_data",
    )

    status_3_label = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_3_value = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_3_count = fields.Integer(
        compute="_compute_dashboard_data",
    )
    status_3_percent = fields.Float(
        compute="_compute_dashboard_data",
    )

    status_4_label = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_4_value = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_4_count = fields.Integer(
        compute="_compute_dashboard_data",
    )
    status_4_percent = fields.Float(
        compute="_compute_dashboard_data",
    )

    status_5_label = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_5_value = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_5_count = fields.Integer(
        compute="_compute_dashboard_data",
    )
    status_5_percent = fields.Float(
        compute="_compute_dashboard_data",
    )

    status_6_label = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_6_value = fields.Char(
        compute="_compute_dashboard_data",
    )
    status_6_count = fields.Integer(
        compute="_compute_dashboard_data",
    )
    status_6_percent = fields.Float(
        compute="_compute_dashboard_data",
    )

    def _get_dashboard_filter_domain(self, model, filters=None):
        self.ensure_one()
        if filters is None:
            filters = self.env.context.get("ngo_dashboard_filters") or "{}"
        if isinstance(filters, str):
            filters = json.loads(filters)

        domain = []
        grant_filter = filters.get("grant_id")
        donor_filter = filters.get("donor_id")
        program_area_filter = filters.get("program_area_id")
        sector_filter = filters.get("sector_id")
        scoped_grant_ids = None

        if sector_filter:
            scoped_grant_ids = set(self.env["ngo.grant"].search([
                ("sector_id", "=", int(sector_filter))
            ]).ids)
        if program_area_filter:
            area_grant_ids = set(self.env["ngo.grant"].search([
                ("program_area_id", "=", int(program_area_filter))
            ]).ids)
            scoped_grant_ids = area_grant_ids if scoped_grant_ids is None else scoped_grant_ids & area_grant_ids
        if grant_filter:
            selected_grants = {int(grant_filter)}
            scoped_grant_ids = selected_grants if scoped_grant_ids is None else scoped_grant_ids & selected_grants
        if donor_filter:
            donor_grants = set(
                self.env["ngo.grant.donor.line"]
                .search([("donor_id", "=", int(donor_filter))])
                .mapped("grant_id").ids
            )
            scoped_grant_ids = donor_grants if scoped_grant_ids is None else scoped_grant_ids & donor_grants

        scoped_subgrant_ids = set()
        if scoped_grant_ids is not None:
            scoped_subgrant_ids.update(self.env["ngo.subgrant"].search([
                ("grant_id", "in", list(scoped_grant_ids))
            ]).ids)

        if grant_filter or program_area_filter or sector_filter or donor_filter:
            grant_ids = list(scoped_grant_ids or [])
            if self.model_name == "ngo.grant":
                domain.append(("id", "in", grant_ids))
            elif self.model_name == "ngo.subgrant":
                domain.append(("id", "in", list(scoped_subgrant_ids)))
            elif self.model_name == "ngo.grant.donor":
                if donor_filter:
                    domain.append(("id", "=", int(donor_filter)))
                if grant_filter or program_area_filter:
                    domain.append(("donor_line_ids.grant_id", "in", grant_ids))
            elif "grant_id" in model._fields and "subgrant_id" in model._fields:
                domain.extend([
                    "|",
                    ("grant_id", "in", grant_ids),
                    ("subgrant_id", "in", list(scoped_subgrant_ids)),
                ])
            elif "grant_id" in model._fields:
                domain.append(("grant_id", "in", grant_ids))
            elif "subgrant_id" in model._fields:
                domain.append(("subgrant_id", "in", list(scoped_subgrant_ids)))
            elif "donor_line_ids" in model._fields:
                domain.append(("donor_line_ids.grant_id", "in", grant_ids))
            if donor_filter and "donor_id" in model._fields:
                domain.append(("donor_id", "=", int(donor_filter)))

        selected_status = filters.get("status")
        if selected_status and self.groupby_field in model._fields:
            status_field = model._fields[self.groupby_field]
            if status_field.type == "selection":
                domain.append((self.groupby_field, "=", selected_status))
        return domain

    @api.depends(
        "model_name",
        "groupby_field",
        "action_xmlid",
    )
    @api.depends_context("ngo_dashboard_filters")
    def _compute_dashboard_data(self):
        for dashboard in self:
            values = {
                "total_count": 0,
            }

            for index in range(1, 7):
                values[f"status_{index}_label"] = False
                values[f"status_{index}_value"] = False
                values[f"status_{index}_count"] = 0
                values[f"status_{index}_percent"] = 0.0

            try:
                model = self.env[dashboard.model_name]
            except (KeyError, TypeError):
                dashboard.update(values)
                continue

            try:
                domain = dashboard._get_dashboard_filter_domain(model)
                records = model.search(domain)
                total = len(records)

                values["total_count"] = total

                if not total:
                    dashboard.update(values)
                    continue

                grouped = {}

                for record in records:
                    value = record[dashboard.groupby_field]

                    field = record._fields.get(dashboard.groupby_field)
                    if not field:
                        continue

                    if field.type == "many2one":
                        key = value.id if value else False
                        label = value.display_name if value else "Not Set"
                    elif field.type == "selection":
                        key = value
                        selection = field.selection
                        if callable(selection):
                            selection = selection(record.env)
                        label = dict(selection or []).get(value, value)
                    else:
                        key = value
                        label = value

                    if key is False or key is None:
                        key = False
                        label = "Not Set"

                    if key not in grouped:
                        grouped[key] = {
                            "value": key,
                            "label": label,
                            "count": 0,
                        }

                    grouped[key]["count"] += 1

                statuses = sorted(
                    grouped.values(),
                    key=lambda item: item["count"],
                    reverse=True,
                )[:6]

                for index, status in enumerate(statuses, start=1):
                    percent = (
                        status["count"] / total * 100
                        if total
                        else 0
                    )

                    values[f"status_{index}_label"] = status["label"]
                    values[f"status_{index}_value"] = status["value"]
                    values[f"status_{index}_count"] = status["count"]
                    values[f"status_{index}_percent"] = round(
                        percent,
                        2,
                    )

            except Exception:
                dashboard.update(values)
                continue

            dashboard.update(values)

    def _get_action(self):
        self.ensure_one()

        action = self.env.ref(
            self.action_xmlid,
            raise_if_not_found=False,
        )

        if not action:
            return False

        result = action.read()[0]

        return result

    @api.model
    def can_user_interact(self):
        """Internal users may drill down; target model ACLs still control records."""
        return self.env.user.has_group('base.group_user')

    @api.model
    def get_filter_options(self, grant_id=False, donor_id=False, program_area_id=False, sector_id=False):
        """Return dashboard filter options using the caller's access rights."""
        grants = self.env["ngo.grant"].search([], order="grant_name, id")
        donors = self.env["ngo.grant.donor"].search([], order="name, id")
        program_areas = grants.mapped("program_area_id")
        currency_domain = []
        if program_area_id:
            currency_domain.append(("program_area_id", "=", int(program_area_id)))
        if sector_id:
            currency_domain.append(("sector_id", "=", int(sector_id)))
        if grant_id:
            currency_domain.append(("id", "=", int(grant_id)))
        if donor_id:
            donor_grant_ids = self.env["ngo.grant.donor.line"].search([
                ("donor_id", "=", int(donor_id))
            ]).mapped("grant_id").ids
            currency_domain.append(("id", "in", donor_grant_ids))
        scoped_grants = self.env["ngo.grant"].search(currency_domain)
        currencies = scoped_grants.mapped("currency_id")
        sectors = grants.mapped("sector_id")
        reporting_currency = (
            currencies.name
            if len(currencies) == 1
            else self.env.company.currency_id.name
        )
        statuses = {}
        for dashboard in self.search([]):
            try:
                model = self.env[dashboard.model_name]
                field = model._fields.get(dashboard.groupby_field)
                if not field or field.type != "selection":
                    continue
                selection = field.selection
                if callable(selection):
                    selection = selection(model)
                for value, label in selection or []:
                    statuses.setdefault(str(value), str(label))
            except Exception:
                # A status provider on one dashboard must not prevent the
                # other filter choices and reporting currency from loading.
                continue
        return {
            "sectors": [{"id": sector.id, "name": sector.display_name} for sector in sectors],
            "grants": [{"id": grant.id, "name": grant.grant_name} for grant in grants],
            "donors": [{"id": donor.id, "name": donor.donor_code} for donor in donors],
            "program_areas": [{"id": area.id, "name": area.display_name} for area in program_areas],
            "statuses": [{"value": value, "label": label} for value, label in statuses.items()],
            "reporting_currency": reporting_currency or "",
        }

    @api.model
    def get_executive_summary(self, filters=None):
        """Return executive KPI metrics, health indicators, alerts, and spotlight grants."""
        if filters is None:
            filters = {}
        elif isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except Exception:
                filters = {}

        domain = []
        grant_filter = filters.get("grant_id")
        donor_filter = filters.get("donor_id")
        program_area_filter = filters.get("program_area_id")
        sector_filter = filters.get("sector_id")
        status_filter = filters.get("status")

        if sector_filter:
            domain.append(("sector_id", "=", int(sector_filter)))
        if program_area_filter:
            domain.append(("program_area_id", "=", int(program_area_filter)))
        if grant_filter:
            domain.append(("id", "=", int(grant_filter)))
        if donor_filter:
            donor_grant_ids = self.env["ngo.grant.donor.line"].search([
                ("donor_id", "=", int(donor_filter))
            ]).mapped("grant_id").ids
            domain.append(("id", "in", donor_grant_ids))
        if status_filter:
            domain.append(("state", "=", status_filter))

        grants = self.env["ngo.grant"].search(domain)
        # The dashboard totals include every current grant status, while Odoo's
        # normal active filter keeps archived/inactive grants out of the totals.
        all_grants = self.env["ngo.grant"].search([])
        grant_ids = grants.ids

        company = self.env.company
        currency = company.currency_id
        today = fields.Date.today()

        def to_reporting_currency(grant, amount):
            return grant.currency_id._convert(amount or 0.0, currency, company, today)

        # The funding headline and grant count always represent the full grant
        # portfolio, regardless of the detail filters selected below.
        total_funding = sum(to_reporting_currency(grant, grant.approved_amount) for grant in all_grants)
        total_disbursed = sum(to_reporting_currency(grant, grant.disbursed_amount) for grant in grants)
        approved_grants = all_grants.filtered(lambda grant: grant.state == "approved")
        total_remaining = 0.0
        for grant in approved_grants:
            committed_disbursements = sum(grant.disbursement_ids.filtered(
                lambda item: item.state in ("approved", "processed")
            ).mapped("amount"))
            remaining = max(grant.approved_amount - committed_disbursements, 0.0)
            total_remaining += to_reporting_currency(grant, remaining)
        subgrant_funding = sum(
            to_reporting_currency(grant, grant.subgrant_amount) for grant in grants
        )
        disbursement_rate = round((total_disbursed / total_funding * 100), 1) if total_funding > 0 else 0.0
        approved_funding = sum(to_reporting_currency(grant, grant.approved_amount) for grant in approved_grants)
        remaining_rate = round((total_remaining / approved_funding * 100), 1) if approved_funding > 0 else 0.0

        all_donors = self.env["ngo.grant.donor"].search([])
        all_projects = self.env["ngo.grant.project"].search([])
        scoped_projects = self.env["ngo.grant.project"].search([("grant_id", "in", grant_ids)]) if grant_ids else []
        scoped_subgrants = self.env["ngo.subgrant"].search([("grant_id", "in", grant_ids)]) if grant_ids else []

        grants_count = len(all_grants)
        active_grants_count = len(grants.filtered(lambda g: g.state == "active"))
        under_review_count = len(grants.filtered(lambda g: g.state in ("submitted", "under_review")))
        draft_count = len(grants.filtered(lambda g: g.state == "draft"))
        approved_count = len(approved_grants)
        closed_count = len(grants.filtered(lambda g: g.state == "closed"))

        today = fields.Date.today()
        upcoming_date = today + relativedelta(days=30)

        rep_domain_base = [("grant_id", "in", grant_ids)] if grant_ids else []
        overdue_reports = self.env["ngo.grant.reporting.schedule"].search_count(
            rep_domain_base + [
                ("state", "not in", ["completed", "accepted", "cancelled"]),
                ("report_date", "<", today),
            ]
        )
        upcoming_reports = self.env["ngo.grant.reporting.schedule"].search_count(
            rep_domain_base + [
                ("state", "not in", ["completed", "accepted", "cancelled"]),
                ("report_date", ">=", today),
                ("report_date", "<=", upcoming_date),
            ]
        )

        disb_domain_base = [("grant_id", "in", grant_ids)] if grant_ids else []
        pending_disbursements = self.env["ngo.grant.disbursement"].search_count(
            disb_domain_base + [("state", "in", ["draft", "submitted"])]
        )

        comp_domain_base = [("grant_id", "in", grant_ids)] if grant_ids else []
        overdue_compliance = self.env["ngo.grant.compliance"].search_count(
            comp_domain_base + [
                ("state", "not in", ["compliant", "waived", "cancelled"]),
                ("due_date", "<", today),
            ]
        )

        currency_symbol = currency.symbol or currency.name or "$"
        currency_position = currency.position or "before"

        top_grants_records = grants.sorted(key=lambda g: g.approved_amount, reverse=True)[:5]
        top_grants = []
        for g in top_grants_records:
            donor_name = g.donor_line_ids[:1].donor_id.name if g.donor_line_ids else "Various Donors"
            pct = round((g.disbursed_amount / g.approved_amount * 100), 1) if g.approved_amount > 0 else 0.0
            top_grants.append({
                "id": g.id,
                "name": g.grant_name,
                "number": g.grant_number or f"G-{g.id:04d}",
                "state": g.state or "draft",
                "state_label": dict(g._fields["state"].selection).get(g.state, g.state),
                "donor_name": donor_name,
                "approved_amount": g.approved_amount,
                "disbursed_amount": g.disbursed_amount,
                "remaining_amount": g.remaining_amount,
                "disbursement_rate": pct,
                "end_date": str(g.end_date) if g.end_date else False,
            })

        return {
            "total_funding": total_funding,
            "total_disbursed": total_disbursed,
            "total_remaining": total_remaining,
            "subgrant_funding": subgrant_funding,
            "disbursement_rate": disbursement_rate,
            "remaining_rate": remaining_rate,
            "grants_count": grants_count,
            "active_grants_count": active_grants_count,
            "under_review_count": under_review_count,
            "draft_count": draft_count,
            "approved_count": approved_count,
            "closed_count": closed_count,
            "donors_count": len(all_donors),
            "projects_count": len(scoped_projects) if grant_ids else len(all_projects),
            "subgrants_count": len(scoped_subgrants),
            "overdue_reports": overdue_reports,
            "upcoming_reports": upcoming_reports,
            "pending_disbursements": pending_disbursements,
            "overdue_compliance": overdue_compliance,
            "currency_symbol": currency_symbol,
            "currency_position": currency_position,
            "currency_name": currency.name or "",
            "top_grants": top_grants,
        }

    @api.model
    def action_open_active_grants(self, filters=None):
        self._check_dashboard_interaction()
        action = self.env.ref("ngo_grant.action_grant", raise_if_not_found=False)
        if not action:
            return False
        res = action.read()[0]
        res["domain"] = [("state", "=", "active")]
        return res

    @api.model
    def action_open_all_grants(self):
        self._check_dashboard_interaction()
        action = self.env.ref("ngo_grant.action_grant", raise_if_not_found=False)
        if not action:
            return False
        result = action.read()[0]
        result["domain"] = []
        result["context"] = {"active_test": True}
        return result

    @api.model
    def action_open_approved_grants(self):
        self._check_dashboard_interaction()
        action = self.env.ref("ngo_grant.action_grant", raise_if_not_found=False)
        if not action:
            return False
        result = action.read()[0]
        result["domain"] = [("state", "=", "approved")]
        result["context"] = {"active_test": True}
        return result

    @api.model
    def action_open_under_review_grants(self, filters=None):
        self._check_dashboard_interaction()
        action = self.env.ref("ngo_grant.action_grant", raise_if_not_found=False)
        if not action:
            return False
        res = action.read()[0]
        res["domain"] = [("state", "in", ["submitted", "under_review"])]
        return res

    @api.model
    def action_open_overdue_reports(self, filters=None):
        self._check_dashboard_interaction()
        action = self.env.ref("ngo_grant.action_reporting_schedule", raise_if_not_found=False)
        if not action:
            return False
        res = action.read()[0]
        today = fields.Date.today()
        res["domain"] = [
            ("state", "not in", ["completed", "accepted", "cancelled"]),
            ("report_date", "<", today),
        ]
        return res

    @api.model
    def action_open_pending_disbursements(self, filters=None):
        self._check_dashboard_interaction()
        action = self.env.ref("ngo_grant.action_disbursement", raise_if_not_found=False)
        if not action:
            return False
        res = action.read()[0]
        res["domain"] = [("state", "in", ["draft", "submitted"])]
        return res

    @api.model
    def action_open_overdue_compliance(self, filters=None):
        self._check_dashboard_interaction()
        action = self.env.ref("ngo_grant.action_compliance", raise_if_not_found=False)
        if not action:
            return False
        res = action.read()[0]
        today = fields.Date.today()
        res["domain"] = [
            ("state", "not in", ["compliant", "waived", "cancelled"]),
            ("due_date", "<", today),
        ]
        return res

    @api.model
    def action_open_grant(self, grant_id):
        self._check_dashboard_interaction()
        return {
            "type": "ir.actions.act_window",
            "name": _("Grant"),
            "res_model": "ngo.grant",
            "res_id": int(grant_id),
            "views": [[False, "form"]],
            "target": "current",
        }

    @api.model
    def action_create_grant(self):
        self._check_dashboard_interaction()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Grant"),
            "res_model": "ngo.grant",
            "views": [[False, "form"]],
            "target": "current",
        }

    @api.model
    def action_create_disbursement(self):
        self._check_dashboard_interaction()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Disbursement"),
            "res_model": "ngo.grant.disbursement",
            "views": [[False, "form"]],
            "target": "current",
        }

    @api.model
    def action_open_export_wizard(self):
        self._check_dashboard_interaction()
        action = self.env.ref("ngo_grant.action_grant_export_wizard", raise_if_not_found=False)
        if not action:
            return False
        return action.read()[0]

    def _check_dashboard_interaction(self):
        if not self.can_user_interact():
            raise AccessError(_('Only internal users can open records from the dashboard.'))

    def action_open_all(self, filters=None):
        self.ensure_one()
        self._check_dashboard_interaction()

        action = self._get_action()

        if not action:
            return False

        action["domain"] = self._merge_filter_domain(
            action.get("domain"),
            self._get_dashboard_filter_domain(self.env[self.model_name], filters),
        )
        return action

    def _merge_filter_domain(self, action_domain, filter_domain):
        self.ensure_one()
        if isinstance(action_domain, str):
            try:
                action_domain = safe_eval(action_domain or "[]", {"uid": self.env.uid, "context": self.env.context})
            except Exception:
                action_domain = []
        if not isinstance(action_domain, list):
            action_domain = []
        return action_domain + filter_domain

    def _action_open_status(self, index, filters=None):
        self.ensure_one()
        self._check_dashboard_interaction()

        action = self._get_action()

        if not action:
            return False

        value = self[f"status_{index}_value"]

        # False represents the "Not Set" bucket and is a valid
        # domain value in Odoo.
        if not self[f"status_{index}_label"]:
            return False

        status_domain = [
            (
                self.groupby_field,
                "=",
                value,
            )
        ]
        action["domain"] = self._merge_filter_domain(
            action.get("domain"),
            self._get_dashboard_filter_domain(self.env[self.model_name], filters) + status_domain,
        )

        return action

    def action_status_1(self, filters=None):
        return self._action_open_status(1, filters)

    def action_status_2(self, filters=None):
        return self._action_open_status(2, filters)

    def action_status_3(self, filters=None):
        return self._action_open_status(3, filters)

    def action_status_4(self, filters=None):
        return self._action_open_status(4, filters)

    def action_status_5(self, filters=None):
        return self._action_open_status(5, filters)

    def action_status_6(self, filters=None):
        return self._action_open_status(6, filters)
