# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError
from dateutil.relativedelta import relativedelta

class NgoGrantDocument(models.Model):
    """NGO Grant Document model.
    
    Stores grant-related documents such as Grant Agreement, Amendment Letter, Donor Approval, Audit Report, Signed Contract, and Compliance Documents.
    """
    
    _name = 'ngo.grant.document'
    _description = 'NGO Grant Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'document_date desc'
    
    # References
    grant_id = fields.Many2one(
        'ngo.grant',
        string='Grant',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Associated grant',
    )
    
    amendment_id = fields.Many2one(
        'ngo.grant.amendment',
        string='Amendment',
        ondelete='cascade',
        tracking=True,
        help='Associated amendment (if applicable)',
    )
    
    compliance_id = fields.Many2one(
        'ngo.grant.compliance',
        string='Compliance',
        ondelete='cascade',
        tracking=True,
        help='Associated compliance item (if applicable)',
    )
    
    reporting_schedule_id = fields.Many2one(
        'ngo.grant.reporting.schedule',
        string='Reporting Schedule',
        ondelete='cascade',
        tracking=True,
        help='Associated reporting schedule (if applicable)',
    )
    
    # Identification
    document_number = fields.Char(
        string='Document Number',
        copy=False,
        tracking=True,
        help='Unique document number',
    )
    
    name = fields.Char(
        string='Document Name',
        required=True,
        tracking=True,
        help='Document name',
    )
    
    document_id = fields.Many2one(
        'documents.document',
        string='Document',
        tracking=True,
        help='Linked Odoo document',
    )
    
    document_type = fields.Selection([
        ('grant_agreement', 'Grant Agreement'),
        ('amendment_letter', 'Amendment Letter'),
        ('donor_approval', 'Donor Approval'),
        ('audit_report', 'Audit Report'),
        ('signed_contract', 'Signed Contract'),
        ('compliance_document', 'Compliance Document'),
        ('financial_report', 'Financial Report'),
        ('narrative_report', 'Narrative Report'),
        ('procurement_document', 'Procurement Document'),
        ('other', 'Other'),
    ],
        string='Document Type',
        required=True,
        tracking=True,
        help='Type of document',
    )
    
    category = fields.Selection([
        ('legal', 'Legal'),
        ('financial', 'Financial'),
        ('technical', 'Technical'),
        ('compliance', 'Compliance'),
        ('reporting', 'Reporting'),
        ('procurement', 'Procurement'),
        ('monitoring', 'Monitoring'),
        ('other', 'Other'),
    ],
        string='Category',
        tracking=True,
        help='Document category',
    )
    
    confidentiality = fields.Selection([
        ('public', 'Public'),
        ('internal', 'Internal'),
        ('confidential', 'Confidential'),
        ('restricted', 'Restricted'),
    ],
        string='Confidentiality',
        default='internal',
        tracking=True,
        help='Document confidentiality level',
    )
    
    # Document
    attachment = fields.Binary(
        string='Document File',
        required=True,
        tracking=True,
        help='Upload the document file',
    )
    
    file_name = fields.Char(
        string='File Name',
        tracking=True,
        help='Name of the uploaded file',
    )
    
    file_size = fields.Integer(
        string='File Size (bytes)',
        readonly=True,
        help='Size of the uploaded file in bytes',
    )
    
    file_url = fields.Char(
        string='File URL',
        compute='_compute_file_url',
        store=False,
        help='URL to download the file',
    )
    
    mimetype = fields.Char(
        string='MIME Type',
        readonly=True,
        help='File MIME type',
    )
    
    # Dates
    document_date = fields.Date(
        string='Document Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date of the document',
    )
    
    expiry_date = fields.Date(
        string='Expiry Date',
        tracking=True,
        help='Document expiry date (if applicable)',
    )
    
    effective_date = fields.Date(
        string='Effective Date',
        tracking=True,
        help='Date when document becomes effective',
    )
    
    # Approval
    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=False,
        tracking=True,
        help='Whether document requires approval',
    )
    
    approved = fields.Boolean(
        string='Approved',
        default=False,
        readonly=True,
        tracking=True,
        help='Whether document is approved',
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        tracking=True,
        help='User who approved the document',
    )
    
    approval_date = fields.Date(
        string='Approval Date',
        tracking=True,
        help='Date when document was approved',
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ],
        string='State',
        default='draft',
        tracking=True,
        help='Document status',
    )
    
    # Details
    description = fields.Text(
        string='Description',
        help='Document description',
    )
    
    version = fields.Char(
        string='Version',
        default='1.0',
        tracking=True,
        help='Document version',
    )
    
    # Access
    is_public = fields.Boolean(
        string='Public',
        default=False,
        help='Whether document is publicly accessible',
    )
    
    is_confidential = fields.Boolean(
        string='Confidential',
        default=False,
        help='Whether document is confidential',
    )
    
    mandatory = fields.Boolean(
        string='Mandatory',
        default=False,
        tracking=True,
        help='Whether document is mandatory',
    )
    
    submitted_to_donor = fields.Boolean(
        string='Submitted to Donor',
        default=False,
        tracking=True,
        help='Whether document has been submitted to donor',
    )
    
    donor_submission_date = fields.Date(
        string='Donor Submission Date',
        tracking=True,
        help='Date when document was submitted to donor',
    )
    
    # Monitoring - Computed fields
    is_expired = fields.Boolean(
        string='Is Expired',
        compute='_compute_is_expired',
        store=True,
        help='Whether document is expired',
    )
    
    days_to_expiry = fields.Integer(
        string='Days to Expiry',
        compute='_compute_days_to_expiry',
        store=True,
        help='Days until document expires',
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional notes',
    )
    
    @api.constrains('expiry_date')
    def _check_expiry_date(self):
        """Validate expiry date."""
        for document in self:
            if document.expiry_date and document.expiry_date < document.document_date:
                raise ValidationError(_('Expiry Date cannot be before Document Date.'))
    
    @api.constrains('is_public', 'is_confidential')
    def _check_access_flags(self):
        """Validate access flags."""
        for document in self:
            if document.is_public and document.is_confidential:
                raise ValidationError(_('Document cannot be both public and confidential.'))

    @api.onchange('is_public')
    def _onchange_is_public(self):
        for document in self:
            if document.is_public:
                document.is_confidential = False

    @api.onchange('is_confidential')
    def _onchange_is_confidential(self):
        for document in self:
            if document.is_confidential:
                document.is_public = False
    
    def _compute_file_url(self):
        """Compute file URL for download."""
        for document in self:
            if document.attachment:
                document.file_url = f'/web/content/{document._name}/{document.id}/attachment/{document.file_name or document.name}'
            else:
                document.file_url = False
    
    @api.depends('expiry_date')
    def _compute_is_expired(self):
        """Compute whether document is expired."""
        for document in self:
            if document.expiry_date:
                document.is_expired = document.expiry_date < fields.Date.today()
            else:
                document.is_expired = False
    
    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        """Compute days until expiry."""
        for document in self:
            if document.expiry_date and document.expiry_date >= fields.Date.today():
                document.days_to_expiry = (document.expiry_date - fields.Date.today()).days
            else:
                document.days_to_expiry = 0
    
    @api.onchange('attachment')
    def _onchange_attachment(self):
        """Auto-detect file size and MIME type when attachment is uploaded."""
        if self.attachment:
            # Calculate file size (bytes)
            if isinstance(self.attachment, bytes):
                self.file_size = len(self.attachment)
            else:
                # For base64 encoded strings
                import base64
                try:
                    self.file_size = len(base64.b64decode(self.attachment))
                except:
                    self.file_size = 0
            
            # Auto-detect MIME type based on file name
            if self.file_name:
                import mimetypes
                mime_type, _ = mimetypes.guess_type(self.file_name)
                self.mimetype = mime_type or 'application/octet-stream'
    
    # Business Methods
    def action_submit(self):
        """Submit document."""
        self._check_manager_access()
        self.with_context(allow_document_workflow_change=True).write({'state': 'submitted'})
        self.message_post(body=_('Document submitted for approval.'))
    
    def action_approve(self):
        """Approve document."""
        self._check_manager_access()
        self.with_context(allow_document_workflow_change=True).write({
            'state': 'approved',
            'approved': True,
            'approved_by': self.env.user.id,
            'approval_date': fields.Date.today(),
        })
        self.message_post(body=_('Document approved.'))
    
    def action_reject(self):
        """Reject document."""
        self._check_manager_access()
        self.with_context(allow_document_workflow_change=True).write({'state': 'rejected'})
        self.message_post(body=_('Document rejected.'))
    
    def action_mark_expired(self):
        """Mark as expired."""
        self._check_manager_access()
        self.with_context(allow_document_workflow_change=True).write({'state': 'expired'})
        self.message_post(body=_('Document marked as expired.'))

    def _check_manager_access(self):
        if not self.env.is_admin() and not self.env.user.has_group('ngo_grant.group_ngo_manager'):
            raise AccessError(_('Only NGO Grant Managers can perform this action.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create document with chatter message."""
        for vals in vals_list:
            if vals.get('state') and vals['state'] != 'draft':
                raise AccessError(_('New documents must start in Draft.'))
            if vals.get('approved') or vals.get('approved_by') or vals.get('approval_date'):
                raise AccessError(_('Document approval status is set automatically by the approval action.'))
        documents = super(NgoGrantDocument, self).create(vals_list)
        for document in documents:
            document.message_post(
                body=_('Document %(name)s uploaded') % {'name': document.name}
            )
        return documents

    def write(self, vals):
        protected_fields = {'state', 'approved', 'approved_by', 'approval_date'}
        if protected_fields.intersection(vals) and not self.env.context.get('allow_document_workflow_change'):
            raise AccessError(_('Document approval status can only be changed through the workflow actions.'))
        return super().write(vals)
    
    @api.model
    def check_document_expiry(self):
        """Check for expired documents and send notifications."""
        today = fields.Date.today()
        warning_date = today + relativedelta(days=30)
        
        expiring_documents = self.search([
            ('expiry_date', '<=', warning_date),
            ('expiry_date', '>=', today),
            ('state', 'in', ['approved', 'active']),
        ])
        
        for document in expiring_documents:
            document.message_post(
                body=_('Document is expiring on %(date)s') % {'date': document.expiry_date}
            )
        
        expired_documents = self.search([
            ('expiry_date', '<', today),
            ('state', 'in', ['approved', 'active']),
        ])
        
        for document in expired_documents:
            document.with_context(allow_document_workflow_change=True).write({'state': 'expired'})
            document.message_post(
                body=_('Document expired on %(date)s') % {'date': document.expiry_date}
            )
    
    @api.onchange('document_id')
    def _onchange_document_id(self):
        """Sync fields from documents.document when selected."""
        for document in self:
            if document.document_id:
                doc = document.document_id
                if not document.name:
                    document.name = doc.name
                if not document.attachment and doc.attachment:
                    document.attachment = doc.attachment
                if not document.file_name and doc.name:
                    document.file_name = doc.name
                if not document.mimetype and doc.mimetype:
                    document.mimetype = doc.mimetype
                if not document.file_size and doc.size:
                    document.file_size = doc.size
    
    def action_link_to_document(self):
        """Link this grant document to documents.document."""
        for document in self:
            if not document.document_id and document.attachment:
                # Create or link to documents.document
                doc_vals = {
                    'name': document.name,
                    'attachment': document.attachment,
                    'mimetype': document.mimetype,
                    'folder_id': self.env.ref('documents.document_folder_root').id if self.env.ref('documents.document_folder_root', raise_if_not_found=False) else False,
                }
                doc = self.env['documents.document'].create(doc_vals)
                document.write({'document_id': doc.id})
                document.message_post(body=_('Linked to document %s') % doc.name)
