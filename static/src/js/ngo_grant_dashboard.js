/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DASHBOARD_FIELDS = [
    "id",
    "name",
    "description",
    "sequence",
    "model_name",
    "action_xmlid",
    "groupby_field",
    "chart_type",
    "color",
    "icon",
    "total_count",
    "chart_style",
];

for (let index = 1; index <= 6; index++) {
    DASHBOARD_FIELDS.push(
        `status_${index}_label`,
        `status_${index}_value`,
        `status_${index}_count`,
        `status_${index}_percent`,
    );
}

export class NgoGrantDashboard extends Component {
    static template = "ngo_grant.NgoGrantDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            refreshing: false,
            canInteract: false,
            dashboards: [],
            filters: { programAreaId: "", status: "", grantId: "", donorId: "" },
            filterOptions: { program_areas: [], statuses: [], grants: [], donors: [] },
        });

        onWillStart(() => this.loadDashboard());
    }

    notify(message, type = "info") {
        if (this.notification) {
            this.notification.add(message, { type });
        } else {
            console.warn(message);
        }
    }

    async loadDashboard() {
        this.state.loading = true;

        try {
            this.state.canInteract = await this.orm.call(
                'ngo.grant.dashboard',
                'can_user_interact',
                [],
            );
            try {
                this.state.filterOptions = await this.orm.call(
                    "ngo.grant.dashboard",
                    "get_filter_options",
                    [
                        this.state.filters.grantId,
                        this.state.filters.donorId,
                        this.state.filters.programAreaId,
                    ],
                );
            } catch (error) {
                console.warn("NGO Grant Dashboard filter options unavailable:", error);
            }
            const dashboards = await this.orm.searchRead(
                "ngo.grant.dashboard",
                [],
                DASHBOARD_FIELDS,
                {
                    order: "sequence, id",
                    context: {
                        ngo_dashboard_filters: JSON.stringify({
                            program_area_id: this.state.filters.programAreaId,
                            status: this.state.filters.status,
                            grant_id: this.state.filters.grantId,
                            donor_id: this.state.filters.donorId,
                        }),
                    },
                },
            );

            this.state.dashboards = dashboards.map((dashboard) =>
                this.prepareDashboard(dashboard)
            );
        } catch (error) {
            console.error("NGO Grant Dashboard loading error:", error);
            this.state.dashboards = [];
            this.notify(
                "Unable to load the NGO Grant dashboard.",
                "danger",
            );
        } finally {
            this.state.loading = false;
        }
    }

    async refreshDashboard() {
        if (this.state.refreshing) {
            return;
        }

        this.state.refreshing = true;
        try {
            await this.loadDashboard();
            this.notify("Dashboard refreshed.", "success");
        } finally {
            this.state.refreshing = false;
        }
    }

    async onFilterChange(field, value) {
        this.state.filters[field] = value;
        await this.loadDashboard();
    }

    getDashboardFilterContext() {
        return {
            ngo_dashboard_filters: JSON.stringify(this.getDashboardFilters()),
        };
    }

    getDashboardFilters() {
        return {
            program_area_id: this.state.filters.programAreaId,
            status: this.state.filters.status,
            grant_id: this.state.filters.grantId,
            donor_id: this.state.filters.donorId,
        };
    }

    prepareDashboard(dashboard) {
        const statuses = [];

        for (let index = 1; index <= 6; index++) {
            const label = dashboard[`status_${index}_label`];
            const value = dashboard[`status_${index}_value`];
            const count = Number(dashboard[`status_${index}_count`] || 0);
            const percent = Number(dashboard[`status_${index}_percent`] || 0);

            if (label || value) {
                statuses.push({
                    index,
                    label: label || value || "Unknown",
                    value,
                    count,
                    percent,
                });
            }
        }

        return {
            ...dashboard,
            total_count: Number(dashboard.total_count || 0),
            statuses,
        };
    }

    getDashboardClass(dashboard) {
        const name = (dashboard.name || "").toLowerCase();

        if (name.includes("grant")) {
            return "ngo-dashboard-panel--large";
        }
        if (name.includes("donor")) {
            return "ngo-dashboard-panel--large";
        }
        if (name.includes("report")) {
            return "ngo-dashboard-panel--large";
        }
        if (name.includes("project")) {
            return "ngo-dashboard-panel--medium";
        }
        if (name.includes("disbursement")) {
            return "ngo-dashboard-panel--medium";
        }
        if (name.includes("compliance")) {
            return "ngo-dashboard-panel--medium";
        }
        if (name.includes("amendment")) {
            return "ngo-dashboard-panel--small";
        }
        if (name.includes("document")) {
            return "ngo-dashboard-panel--small";
        }
        return "ngo-dashboard-panel--medium";
    }

    getChartType(dashboard) {
        return dashboard.chart_type || "status";
    }

    getColor(index, dashboard) {
        // Use the dashboard accent for the first slice, then distinct
        // status colors so donut/pie categories never collapse into one color.
        const colors = [
            dashboard.color || "#714B67",
            "#9CA3AF",
            "#5B8FF9",
            "#F0AD4E",
            "#D9534F",
            "#875A7B",
        ];
        return colors[index % colors.length];
    }

    getStatusStyle(status, dashboard) {
        const percentage = Math.max(
            0,
            Math.min(100, Number(status.percent || 0)),
        );

        return `width:${percentage}%;background-color:${dashboard.color || "#714B67"};`;
    }

    getBarHeight(statuses, status) {
        if (!statuses.length) {
            return 0;
        }

        const maximum = Math.max(
            ...statuses.map((item) => Number(item.count || 0)),
            1,
        );

        return Math.max(
            8,
            (Number(status.count || 0) / maximum) * 100,
        );
    }

    getBarStyle(status, statuses, dashboard) {
        return `height:${this.getBarHeight(statuses, status)}%;background-color:${dashboard.color || "#714B67"};`;
    }

    getDonutStyle(statuses, dashboard) {
        if (!statuses.length) {
            return "background:#e9ecef;";
        }

        let current = 0;
        const parts = statuses.map((status, index) => {
            const start = current;
            const end = current + Number(status.percent || 0);
            current = end;
            return `${this.getColor(index, dashboard)} ${start}% ${end}%`;
        });

        return `background:conic-gradient(${parts.join(",")});`;
    }

    async openAll(dashboard) {
        if (!this.state.canInteract || !dashboard?.id) {
            return;
        }

        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_all",
                [[dashboard.id]],
                { context: this.getDashboardFilterContext() },
            );

            if (result) {
                await this.action.doAction(result);
            } else {
                this.notify("Unable to open the records.", "warning");
            }
        } catch (error) {
            console.error("Unable to open dashboard records:", error);
            this.notify("Unable to open the records.", "danger");
        }
    }

    async openStatus(dashboard, status) {
        if (!this.state.canInteract || !dashboard?.id || !status?.index) {
            return;
        }

        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                `action_status_${status.index}`,
                [[dashboard.id]],
                { context: this.getDashboardFilterContext() },
            );

            if (result) {
                await this.action.doAction(result);
            } else {
                this.notify(
                    `No records found for ${status.label}.`,
                    "warning",
                );
            }
        } catch (error) {
            console.error(
                `Unable to open ${dashboard.name} status:`,
                error,
            );
            this.notify(
                "Unable to open the selected records.",
                "danger",
            );
        }
    }
}

registry.category("actions").add(
    "ngo_grant_dashboard",
    NgoGrantDashboard,
);
