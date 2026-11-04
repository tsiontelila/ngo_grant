from odoo.tests.common import TransactionCase


class TestDonorCategory(TransactionCase):

    def test_donor_category_has_mail_thread_api(self):
        model = self.env['ngo.grant.donor.category']
        self.assertTrue(hasattr(model, '_get_thread_with_access'))

    def test_export_summary_report_reference_is_valid(self):
        grant = self.env['ngo.grant'].create({
            'grant_number': 'G-001',
            'grant_name': 'Test Grant',
            'currency_id': self.env.company.currency_id.id,
            'approved_amount': 1000,
        })
        wizard = self.env['ngo.grant.export.wizard'].create({
            'grant_id': grant.id,
            'report_type': 'summary',
            'export_format': 'pdf',
        })

        action = wizard._export_pdf(grant)

        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(action['report_name'], 'ngo_grant.grant_summary_report_template')

    def test_reset_disbursement_restores_linked_negative_amendment(self):
        grant = self.env['ngo.grant'].create({
            'grant_number': 'G-RESET-001',
            'grant_name': 'Reset Disbursement Grant',
            'currency_id': self.env.company.currency_id.id,
            'approved_amount': 10000,
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        })
        disbursement = self.env['ngo.grant.disbursement'].create({
            'grant_id': grant.id,
            'amount': 1000,
        })
        amendment = self.env['ngo.grant.amendment'].create({
            'grant_id': grant.id,
            'disbursement_id': disbursement.id,
            'amendment_name': 'Reverse accidental reduction',
            'description': 'Temporary reduction linked to the disbursement.',
            'amendment_type': 'budget_revision',
            'amount_change': -5000,
            'original_end_date': grant.end_date,
        })

        amendment.action_approve()
        self.assertEqual(grant.approved_amount, 5000)

        disbursement.action_approve()
        disbursement.action_process()
        self.assertEqual(disbursement.state, 'processed')

        disbursement.action_draft()

        self.assertEqual(disbursement.state, 'draft')
        self.assertEqual(amendment.state, 'draft')
        self.assertEqual(grant.approved_amount, 10000)
