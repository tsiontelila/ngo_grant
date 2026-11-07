# -*- coding: utf-8 -*-

import base64
import csv
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class GrantExportWizard(models.TransientModel):
    """Wizard for exporting grant financial data in multiple formats.
    
    Supports: Excel (.xlsx), CSV, HTML, PDF (via existing QWeb actions).
    """

    _name = 'ngo.grant.export.wizard'
    _description = 'Grant Export Wizard'

    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        readonly=True,
    )

    report_type = fields.Selection([
        ('summary', 'Grant Summary'),
        ('income_statement', 'Income Statement'),
        ('balance_sheet', 'Balance Sheet'),
        ('cash_flow', 'Cash Flow Statement'),
        ('fund_analysis', 'Fund Analysis (Restricted/Unrestricted)'),
        ('donor_statement', 'Donor Statement'),
        ('budget_vs_actual', 'Budget vs. Actual'),
        ('audit_trail', 'Audit Trail'),
    ], string='Report Type', required=True, default='summary')

    export_format = fields.Selection([
        ('pdf', 'PDF'),
        ('excel', 'Excel (.xlsx)'),
        ('csv', 'CSV'),
        ('html', 'HTML'),
    ], string='Export Format', required=True, default='pdf')

    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')
    include_disbursements = fields.Boolean(string='Include Disbursements', default=True)
    include_milestones = fields.Boolean(string='Include Milestones', default=True)
    include_budget_periods = fields.Boolean(string='Include Fiscal Sub-Budgets', default=True)
    include_audit_trail = fields.Boolean(string='Include Audit Trail', default=False)

    export_file = fields.Binary(string='Download File', readonly=True)
    export_filename = fields.Char(string='Filename', readonly=True)

    def action_export(self):
        """Export grant report in selected format."""
        self.ensure_one()
        grant = self.grant_id

        if self.export_format == 'pdf':
            return self._export_pdf(grant)
        elif self.export_format == 'excel':
            return self._export_excel(grant)
        elif self.export_format == 'csv':
            return self._export_csv(grant)
        elif self.export_format == 'html':
            return self._export_html(grant)
        else:
            raise UserError(_('Unknown export format: %s') % self.export_format)

    def _export_pdf(self, grant):
        """Redirect to the appropriate PDF QWeb report."""
        report_map = {
            'summary': 'ngo_grant.report_grant_summary',
            'income_statement': 'ngo_grant.action_grant_income_statement',
            'balance_sheet': 'ngo_grant.action_grant_balance_sheet',
            'cash_flow': 'ngo_grant.action_grant_cash_flow',
            'fund_analysis': 'ngo_grant.action_grant_fund_analysis',
            'donor_statement': 'ngo_grant.action_grant_donor_statement',
            'budget_vs_actual': 'ngo_grant.action_grant_income_statement',  # best fit
            'audit_trail': 'ngo_grant.report_grant_summary',
        }
        action_ref = report_map.get(self.report_type, 'ngo_grant.report_grant_summary')
        report_action = self.env.ref(action_ref)
        return report_action.report_action(grant)

    def _get_grant_data_rows(self, grant):
        """Build list-of-dict rows based on report_type."""
        rows = []
        rt = self.report_type

        if rt == 'summary':
            rows = [
                {'Field': 'Grant Number', 'Value': grant.grant_number},
                {'Field': 'Grant Name', 'Value': grant.grant_name},
                {'Field': 'Short Name', 'Value': grant.short_name or ''},
                {'Field': 'Restriction Type', 'Value': grant.restriction_type},
                {'Field': 'Status', 'Value': grant.state},
                {'Field': 'Start Date', 'Value': str(grant.start_date)},
                {'Field': 'End Date', 'Value': str(grant.end_date)},
                {'Field': 'Approved Amount', 'Value': grant.approved_amount},
                {'Field': 'Total Contributed', 'Value': grant.total_contributed_amount},
                {'Field': 'Disbursed Amount', 'Value': grant.disbursed_amount},
                {'Field': 'Remaining Amount', 'Value': grant.remaining_amount},
                {'Field': 'Subgrant Count', 'Value': len(grant.subgrant_ids)},
                {'Field': 'Total Subgrant Amount', 'Value': grant.subgrant_amount},
                {'Field': 'Currency', 'Value': grant.currency_id.name},
            ]
            for subgrant in grant.subgrant_ids:
                rows.extend([
                    {'Field': 'Subgrant: %s' % subgrant.grant_number, 'Value': subgrant.grant_name},
                    {'Field': 'Subgrant Approved Amount: %s' % subgrant.grant_number, 'Value': subgrant.approved_amount},
                    {'Field': 'Subgrant Disbursed Amount: %s' % subgrant.grant_number, 'Value': subgrant.disbursed_amount},
                    {'Field': 'Subgrant Remaining Amount: %s' % subgrant.grant_number, 'Value': subgrant.remaining_amount},
                ])

        elif rt == 'income_statement':
            rows = [
                {'Description': 'Total Grant Approved', 'Amount': grant.approved_amount, 'Currency': grant.currency_id.name},
                {'Description': 'Total Donor Contributions', 'Amount': grant.total_contributed_amount, 'Currency': grant.currency_id.name},
                {'Description': 'Total Subgrant Allocations', 'Amount': grant.subgrant_amount, 'Currency': grant.currency_id.name},
            ]
            for subgrant in grant.subgrant_ids:
                rows.append({
                    'Description': 'Subgrant: %s - %s' % (subgrant.grant_number, subgrant.grant_name),
                    'Amount': subgrant.approved_amount,
                    'Currency': subgrant.currency_id.name,
                    'Disbursed': subgrant.disbursed_amount,
                    'Remaining': subgrant.remaining_amount,
                    'Status': subgrant.state,
                })
            if self.include_budget_periods:
                for bp in grant.budget_period_ids:
                    rows.append({
                        'Description': 'Fiscal Period: %s' % bp.name,
                        'Allocated': bp.allocated_amount,
                        'Spent': bp.spent_amount,
                        'Remaining': bp.remaining_amount,
                        'Utilization %': round(bp.utilization_rate, 1),
                        'Currency': grant.currency_id.name,
                    })

        elif rt == 'cash_flow':
            for dl in grant.donor_line_ids:
                rows.append({
                    'Type': 'INFLOW',
                    'Donor': dl.donor_id.name if dl.donor_id else '',
                    'Reference': dl.donor_reference or '',
                    'Amount': dl.contribution_amount,
                    'Currency': grant.currency_id.name,
                    'Date': '',
                    'Status': dl.state,
                })
            for d in grant.disbursement_ids:
                rows.append({
                    'Type': 'OUTFLOW',
                    'Reference': d.name,
                    'Date': str(d.disbursement_date),
                    'Disbursement Type': d.disbursement_type_id.name or d.disbursement_type,
                    'Amount': -d.amount,
                    'Currency': grant.currency_id.name,
                    'Status': d.state,
                })
            for subgrant in grant.subgrant_ids:
                for d in subgrant.disbursement_ids:
                    rows.append({
                        'Type': 'SUBGRANT OUTFLOW',
                        'Reference': '%s / %s' % (subgrant.grant_number, d.name),
                        'Date': str(d.disbursement_date),
                        'Disbursement Type': 'Subgrant Disbursement',
                        'Amount': -d.amount,
                        'Currency': d.currency_id.name,
                        'Status': d.state,
                    })
            rows.append({
                'Type': 'NET POSITION',
                'Reference': 'Remaining Balance',
                'Amount': grant.remaining_amount,
                'Currency': grant.currency_id.name,
            })

        elif rt == 'donor_statement':
            for dl in grant.donor_line_ids:
                rows.append({
                    'Donor Name': dl.donor_id.name if dl.donor_id else '',
                    'Lead Donor': dl.lead_donor,
                    'Donor Reference': dl.donor_reference or '',
                    'Agreement Reference': dl.agreement_reference or '',
                    'Contribution Amount': dl.contribution_amount,
                    'Contribution %': dl.contribution_percentage,
                    'Status': dl.state,
                    'Currency': grant.currency_id.name,
                })
        elif rt == 'budget_vs_actual':
            for bp in grant.budget_period_ids:
                rows.append({
                    'Period': bp.name,
                    'Start Date': str(bp.start_date),
                    'End Date': str(bp.end_date),
                    'Allocated Budget': bp.allocated_amount,
                    'Actual Spent': bp.spent_amount,
                    'Variance': bp.allocated_amount - bp.spent_amount,
                    'Utilization %': round(bp.utilization_rate, 1),
                    'Overrun Rule': bp.overrun_action,
                    'Status': bp.state,
                    'Currency': grant.currency_id.name,
                })

        elif rt == 'audit_trail':
            for log in grant.audit_log_ids:
                rows.append({
                    'Timestamp': str(log.timestamp),
                    'User': log.user_id.name if log.user_id else '',
                    'Field': log.field_description,
                    'Old Value': log.old_value,
                    'New Value': log.new_value,
                    'Action': log.action_type,
                })

        elif rt in ('balance_sheet', 'fund_analysis'):
            rows = [
                {'Field': 'Grant Number', 'Value': grant.grant_number},
                {'Field': 'Restriction Type', 'Value': grant.restriction_type},
                {'Field': 'Approved Amount', 'Value': grant.approved_amount},
                {'Field': 'Disbursed Amount', 'Value': grant.disbursed_amount},
                {'Field': 'Net Receivable Balance', 'Value': grant.remaining_amount},
                {'Field': 'Total Subgrant Allocations', 'Value': grant.subgrant_amount},
                {'Field': 'Currency', 'Value': grant.currency_id.name},
            ]
        return rows

    def _export_excel(self, grant):
        """Generate an Excel .xlsx file using xlsxwriter if available, otherwise openpyxl."""
        try:
            import xlsxwriter
            use_xlsxwriter = True
        except ImportError:
            try:
                import openpyxl
                use_xlsxwriter = False
            except ImportError:
                raise UserError(_(
                    'Excel export requires xlsxwriter or openpyxl. '
                    'Please install one: pip install xlsxwriter'
                ))

        rows = self._get_grant_data_rows(grant)
        if not rows:
            raise UserError(_('No data to export.'))

        headers = list(rows[0].keys())
        output = io.BytesIO()

        if use_xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet(self.report_type[:31])
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#2c5f8a', 'font_color': 'white', 'border': 1})
            row_fmt = workbook.add_format({'border': 1})
            alt_fmt = workbook.add_format({'border': 1, 'bg_color': '#eaf3fb'})

            for col_idx, header in enumerate(headers):
                worksheet.write(0, col_idx, header, header_fmt)
                worksheet.set_column(col_idx, col_idx, 22)

            for row_idx, row_data in enumerate(rows):
                fmt = alt_fmt if row_idx % 2 == 0 else row_fmt
                for col_idx, key in enumerate(headers):
                    val = row_data.get(key, '')
                    worksheet.write(row_idx + 1, col_idx, val, fmt)
            workbook.close()
        else:
            from openpyxl import Workbook
            from openpyxl.styles import PatternFill, Font, Border, Side
            wb = Workbook()
            ws = wb.active
            ws.title = self.report_type[:31]
            header_fill = PatternFill('solid', fgColor='2C5F8A')
            header_font = Font(bold=True, color='FFFFFF')
            ws.append(headers)
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
            for row_data in rows:
                ws.append([row_data.get(h, '') for h in headers])
            wb.save(output)

        content = base64.b64encode(output.getvalue())
        filename = 'grant_%s_%s.xlsx' % (self.report_type, grant.grant_number.replace('/', '-'))
        self.write({'export_file': content, 'export_filename': filename})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ngo.grant.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Download Excel Export'),
        }

    def _export_csv(self, grant):
        """Generate a CSV file."""
        rows = self._get_grant_data_rows(grant)
        if not rows:
            raise UserError(_('No data to export.'))

        output = io.StringIO()
        headers = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
        content = base64.b64encode(output.getvalue().encode('utf-8'))
        filename = 'grant_%s_%s.csv' % (self.report_type, grant.grant_number.replace('/', '-'))
        self.write({'export_file': content, 'export_filename': filename})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ngo.grant.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Download CSV Export'),
        }

    def _export_html(self, grant):
        """Generate an inline HTML report."""
        rows = self._get_grant_data_rows(grant)
        if not rows:
            raise UserError(_('No data to export.'))

        headers = list(rows[0].keys())
        th_cells = ''.join('<th style="background:#2c5f8a;color:white;padding:6px 10px;">%s</th>' % h for h in headers)
        tr_rows = ''
        for i, row in enumerate(rows):
            bg = '#eaf3fb' if i % 2 == 0 else '#ffffff'
            td_cells = ''.join(
                '<td style="padding:5px 10px;border:1px solid #ddd;">%s</td>' % str(row.get(h, ''))
                for h in headers
            )
            tr_rows += '<tr style="background:%s;">%s</tr>' % (bg, td_cells)

        html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>Grant Report: {grant_number}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 30px; }}
  h2 {{ color: #2c5f8a; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
  th {{ border: 1px solid #2c5f8a; }}
  td {{ border: 1px solid #ddd; }}
</style>
</head><body>
<h2>Grant {report_type_label}: {grant_number} — {grant_name}</h2>
<p>Restriction: <strong>{restriction_type}</strong> &nbsp;|&nbsp; Status: <strong>{state}</strong> &nbsp;|&nbsp;
   Period: {start_date} to {end_date}</p>
<table>
  <thead><tr>{th_cells}</tr></thead>
  <tbody>{tr_rows}</tbody>
</table>
<p style="margin-top:20px;font-size:11px;color:#888;">
  Generated by NGO Grant Management System | {grant_number}
</p>
</body></html>""".format(
            grant_number=grant.grant_number,
            grant_name=grant.grant_name,
            report_type_label=dict(self._fields['report_type'].selection).get(self.report_type, self.report_type),
            restriction_type=grant.restriction_type,
            state=grant.state,
            start_date=str(grant.start_date),
            end_date=str(grant.end_date),
            th_cells=th_cells,
            tr_rows=tr_rows,
        )

        content = base64.b64encode(html.encode('utf-8'))
        filename = 'grant_%s_%s.html' % (self.report_type, grant.grant_number.replace('/', '-'))
        self.write({'export_file': content, 'export_filename': filename})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ngo.grant.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Download HTML Export'),
        }
