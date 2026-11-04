# -*- coding: utf-8 -*-

{
    'name': 'NGO Grant Management',
    'version': '19.0.1.0.0',
    'category': 'NGO',
    'summary': 'Grant lifecycle management, donor management, and project funding',
    'description': """
NGO Grant Management Module
===========================
Manages the complete lifecycle of donor-funded grants:
* Grant lifecycle management
* Donor management
* Project funding allocations
* Multi-grant funding support
* Grant agreements and amendments
* Grant periods
* Compliance tracking
* Grant-document management
* Donor reporting metadata
* Integration with Budget, Procurement, HR, MEAL, and Reporting
    """,
    'author': 'Top Technologies by- Natnael Yonas',
    'website': 'https://www.toptech-world.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'contacts',
        'documents',
        'project',
        'hr',
        'ngo_base',
        'ngo_project',
        
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/sequence.xml',
        'data/disbursement_type_data.xml',
        'data/mail_template.xml',
        'data/cron.xml',
        
        # Wizard Views (must load before views that reference wizard action IDs)
        'wizard/grant_amendment_wizard.xml',
        'wizard/grant_export_wizard.xml',
        
        # Views
        'views/grant_views.xml',
        'views/donor_views.xml',
        'views/donor_category_views.xml',
        'views/grant_project_views.xml',
        'views/grant_amendment_views.xml',
        'views/grant_document_views.xml',
        'views/grant_contact_views.xml',
        'views/grant_compliance_views.xml',
        'views/reporting_schedule_views.xml',
        'views/grant_disbursement_views.xml',
        'views/grant_disbursement_type_views.xml',
        
        # Reports
        'reports/grant_report_templates.xml',
        'reports/grant_report.xml',
        'reports/grant_financial_reports.xml',
        'reports/grant_financial_report_actions.xml',

        # Reporting menus
        'views/reporting_views.xml',
    ],
    'demo': [
        'demo/donor_demo.xml',
        'demo/grant_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    "images": ["static/description/icon.png"],
}
