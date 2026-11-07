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

const MODERN_PALETTE = [
    "#6366F1", // Indigo
    "#10B981", // Emerald
    "#06B6D4", // Cyan
    "#F59E0B", // Amber
    "#EF4444", // Rose
    "#8B5CF6", // Violet
    "#EC4899", // Pink
    "#14B8A6", // Teal
    "#3B82F6", // Blue
    "#F97316", // Orange
];

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
            activeTab: "all", // "all", "portfolio", "disbursement", "compliance"
            quickFilter: "all", // "all", "active", "review", "draft"
            dashboards: [],
            summary: {
                total_funding: 0,
                total_disbursed: 0,
                total_remaining: 0,
                subgrant_funding: 0,
                disbursement_rate: 0,
                remaining_rate: 0,
                grants_count: 0,
                active_grants_count: 0,
                under_review_count: 0,
                draft_count: 0,
                approved_count: 0,
                closed_count: 0,
                donors_count: 0,
                projects_count: 0,
                subgrants_count: 0,
                overdue_reports: 0,
                upcoming_reports: 0,
                pending_disbursements: 0,
                overdue_compliance: 0,
                currency_symbol: "$",
                currency_position: "before",
                currency_name: "",
                top_grants: [],
            },
            filters: { sectorId: "", programAreaId: "", status: "", grantId: "", donorId: "" },
            filterOptions: { sectors: [], program_areas: [], statuses: [], grants: [], donors: [] },
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
                "ngo.grant.dashboard",
                "can_user_interact",
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
                        this.state.filters.sectorId,
                    ],
                );
            } catch (error) {
                console.warn("NGO Grant Dashboard filter options unavailable:", error);
            }

            try {
                this.state.summary = await this.orm.call(
                    "ngo.grant.dashboard",
                    "get_executive_summary",
                    [this.getDashboardFilters()],
                );
            } catch (error) {
                console.warn("NGO Grant Dashboard executive summary error:", error);
            }

            const dashboards = await this.orm.searchRead(
                "ngo.grant.dashboard",
                [],
                DASHBOARD_FIELDS,
                {
                    order: "sequence, id",
                    context: this.getDashboardFilterContext(),
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
            this.notify("Dashboard refreshed with latest data.", "success");
        } finally {
            this.state.refreshing = false;
        }
    }

    async onFilterChange(field, value) {
        this.state.filters[field] = value;
        if (field === "status") {
            if (value === "active") this.state.quickFilter = "active";
            else if (value === "under_review") this.state.quickFilter = "review";
            else if (value === "draft") this.state.quickFilter = "draft";
            else if (!value) this.state.quickFilter = "all";
            else this.state.quickFilter = "custom";
        }
        await this.loadDashboard();
    }

    async setQuickFilter(key) {
        this.state.quickFilter = key;
        if (key === "all") {
            this.state.filters.status = "";
        } else if (key === "active") {
            this.state.filters.status = "active";
        } else if (key === "review") {
            this.state.filters.status = "under_review";
        } else if (key === "draft") {
            this.state.filters.status = "draft";
        }
        await this.loadDashboard();
    }

    async resetFilters() {
        this.state.filters = {
            sectorId: "",
            programAreaId: "",
            status: "",
            grantId: "",
            donorId: "",
        };
        this.state.quickFilter = "all";
        await this.loadDashboard();
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    get activeFilterCount() {
        let count = 0;
        if (this.state.filters.sectorId) count++;
        if (this.state.filters.programAreaId) count++;
        if (this.state.filters.status) count++;
        if (this.state.filters.grantId) count++;
        if (this.state.filters.donorId) count++;
        return count;
    }

    getDashboardFilterContext() {
        return {
            ngo_dashboard_filters: JSON.stringify(this.getDashboardFilters()),
        };
    }

    getDashboardFilters() {
        return {
            program_area_id: this.state.filters.programAreaId,
            sector_id: this.state.filters.sectorId,
            status: this.state.filters.status,
            grant_id: this.state.filters.grantId,
            donor_id: this.state.filters.donorId,
        };
    }

    getCategory(dashboard) {
        const model = dashboard.model_name || "";
        if (["ngo.grant", "ngo.grant.donor", "ngo.grant.project"].includes(model)) {
            return "portfolio";
        }
        if (
            [
                "ngo.grant.disbursement",
                "ngo.subgrant",
                "ngo.subgrant.amendment",
                "ngo.subgrant.disbursement",
            ].includes(model)
        ) {
            return "disbursement";
        }
        if (
            [
                "ngo.grant.compliance",
                "ngo.grant.reporting.schedule",
                "ngo.grant.amendment",
                "ngo.grant.document",
            ].includes(model)
        ) {
            return "compliance";
        }
        return "other";
    }

    getCategoryBadge(dashboard) {
        const cat = this.getCategory(dashboard);
        if (cat === "portfolio") return "Portfolio & Governance";
        if (cat === "disbursement") return "Financial & Subgrants";
        if (cat === "compliance") return "Compliance & Schedules";
        return "General";
    }

    get visibleDashboards() {
        let list = this.state.dashboards;
        if (this.state.activeTab !== "all") {
            list = list.filter((d) => this.getCategory(d) === this.state.activeTab);
        }
        return list;
    }

    formatCurrency(amount, compact = false) {
        if (amount === undefined || amount === null) return "0";
        const num = Number(amount) || 0;
        const symbol = this.state.summary.currency_symbol || "$";
        const position = this.state.summary.currency_position || "before";

        let formatted = "";
        if (compact) {
            if (Math.abs(num) >= 1_000_000_000) {
                formatted = (num / 1_000_000_000).toFixed(1) + "B";
            } else if (Math.abs(num) >= 1_000_000) {
                formatted = (num / 1_000_000).toFixed(1) + "M";
            } else if (Math.abs(num) >= 1_000) {
                formatted = (num / 1_000).toFixed(1) + "k";
            } else {
                formatted = Math.round(num).toLocaleString();
            }
        } else {
            formatted = num.toLocaleString(undefined, {
                minimumFractionDigits: 0,
                maximumFractionDigits: 2,
            });
        }

        return position === "after" ? `${formatted} ${symbol}` : `${symbol}${formatted}`;
    }

    formatNumber(num) {
        if (!num && num !== 0) return "0";
        return Number(num).toLocaleString();
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

        if (name.includes("grant") && !name.includes("amendment") && !name.includes("disbursement")) {
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
        if (index === 0 && dashboard && dashboard.color) {
            return dashboard.color;
        }
        return MODERN_PALETTE[index % MODERN_PALETTE.length];
    }

    getStatusStyle(status, dashboard) {
        const percentage = Math.max(
            0,
            Math.min(100, Number(status.percent || 0)),
        );
        const color = this.getColor(status.index - 1, dashboard);
        return `width:${percentage}%;background:${color};`;
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
            12,
            (Number(status.count || 0) / maximum) * 100,
        );
    }

    getBarStyle(status, statuses, dashboard) {
        const color = this.getColor(status.index - 1, dashboard);
        return `height:${this.getBarHeight(statuses, status)}%;background:${color};`;
    }

    getDonutStyle(statuses, dashboard) {
        if (!statuses.length) {
            return "background:#f1f5f9;";
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

    async openAllGrants() {
        if (!this.state.canInteract) {
            return;
        }
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_all_grants",
                [],
            );
            if (result) {
                await this.action.doAction(result);
            }
        } catch (error) {
            console.error("Unable to open all grants:", error);
            this.notify("Unable to open all grants.", "danger");
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

    async createNewGrant() {
        if (!this.state.canInteract) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_create_grant",
                [],
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error creating grant:", error);
        }
    }

    async createNewDisbursement() {
        if (!this.state.canInteract) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_create_disbursement",
                [],
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error creating disbursement:", error);
        }
    }

    async openExportWizard() {
        if (!this.state.canInteract) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_export_wizard",
                [],
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error opening export wizard:", error);
        }
    }

    async openActiveGrants() {
        if (!this.state.canInteract) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_active_grants",
                [],
                { context: this.getDashboardFilterContext() },
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error opening active grants:", error);
        }
    }

    async openUnderReviewGrants() {
        if (!this.state.canInteract) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_under_review_grants",
                [],
                { context: this.getDashboardFilterContext() },
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error opening under review grants:", error);
        }
    }

    async openApprovedGrants() {
        if (!this.state.canInteract) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_approved_grants",
                [],
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error opening approved grants:", error);
            this.notify("Unable to open approved grants.", "danger");
        }
    }

    async openOverdueReports() {
        if (!this.state.canInteract) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_overdue_reports",
                [],
                { context: this.getDashboardFilterContext() },
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error opening overdue reports:", error);
        }
    }

    async openPendingDisbursements() {
        if (!this.state.canInteract) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_pending_disbursements",
                [],
                { context: this.getDashboardFilterContext() },
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error opening pending disbursements:", error);
        }
    }

    async openOverdueCompliance() {
        if (!this.state.canInteract) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_overdue_compliance",
                [],
                { context: this.getDashboardFilterContext() },
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error opening overdue compliance:", error);
        }
    }

    async openGrant(grantId) {
        if (!this.state.canInteract || !grantId) return;
        try {
            const result = await this.orm.call(
                "ngo.grant.dashboard",
                "action_open_grant",
                [grantId],
            );
            if (result) await this.action.doAction(result);
        } catch (error) {
            console.error("Error opening grant:", error);
        }
    }
}

registry.category("actions").add(
    "ngo_grant_dashboard",
    NgoGrantDashboard,
);
