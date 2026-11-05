# -*- coding: utf-8 -*-

import json

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
        scoped_grant_ids = None

        if program_area_filter:
            scoped_grant_ids = set(self.env["ngo.grant"].search([
                ("program_area_id", "=", int(program_area_filter))
            ]).ids)
        if grant_filter:
            selected_grants = {int(grant_filter)}
            scoped_grant_ids = selected_grants if scoped_grant_ids is None else scoped_grant_ids & selected_grants
        if donor_filter:
            donor_grants = set(
                self.env["ngo.grant.donor.line"]
                .search([("donor_id", "=", int(donor_filter))])
                .mapped("grant_id").ids
            )
            donor_subgrant_lines = self.env["ngo.subgrant.donor.line"].search([
                ("donor_id", "=", int(donor_filter))
            ])
            donor_grants.update(donor_subgrant_lines.mapped("subgrant_id.grant_id").ids)
            scoped_grant_ids = donor_grants if scoped_grant_ids is None else scoped_grant_ids & donor_grants

        scoped_subgrant_ids = set()
        if scoped_grant_ids is not None:
            scoped_subgrant_ids.update(self.env["ngo.subgrant"].search([
                ("grant_id", "in", list(scoped_grant_ids))
            ]).ids)
        if donor_filter:
            scoped_subgrant_ids.update(donor_subgrant_lines.mapped("subgrant_id").ids)

        if grant_filter or program_area_filter or donor_filter:
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
    def get_filter_options(self, grant_id=False, donor_id=False, program_area_id=False):
        """Return dashboard filter options using the caller's access rights."""
        grants = self.env["ngo.grant"].search([], order="grant_name, id")
        donors = self.env["ngo.grant.donor"].search([], order="name, id")
        program_areas = grants.mapped("program_area_id")
        currency_domain = []
        if program_area_id:
            currency_domain.append(("program_area_id", "=", int(program_area_id)))
        if grant_id:
            currency_domain.append(("id", "=", int(grant_id)))
        if donor_id:
            donor_grant_ids = self.env["ngo.grant.donor.line"].search([
                ("donor_id", "=", int(donor_id))
            ]).mapped("grant_id").ids
            currency_domain.append(("id", "in", donor_grant_ids))
        scoped_grants = self.env["ngo.grant"].search(currency_domain)
        currencies = scoped_grants.mapped("currency_id")
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
            "grants": [{"id": grant.id, "name": grant.grant_name} for grant in grants],
            "donors": [{"id": donor.id, "name": donor.donor_code} for donor in donors],
            "program_areas": [{"id": area.id, "name": area.display_name} for area in program_areas],
            "statuses": [{"value": value, "label": label} for value, label in statuses.items()],
            "reporting_currency": reporting_currency or "",
        }

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
