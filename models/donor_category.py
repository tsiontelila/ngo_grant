# -*- coding: utf-8 -*-

from odoo import models, fields


class NgoGrantDonorCategory(models.Model):
    _name = 'ngo.grant.donor.category'
    _description = 'NGO Grant Donor Category'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True,
        help='Name of the donor category',
    )
    
    description = fields.Text(
        string='Description',
        help='Description of this donor category',
    )
    
    color = fields.Integer(
        string='Color Index',
        help='Color index for visual categorization',
    )
    
    donor_ids = fields.Many2many(
        'ngo.grant.donor',
        'donor_category_rel',
        'category_id',
        'donor_id',
        string='Donors',
        help='Donors in this category',
    )
    
    donor_count = fields.Integer(
        string='Donor Count',
        compute='_compute_donor_count',
        store=False,
    )
    
    def _compute_donor_count(self):
        """Compute the number of donors in this category."""
        for category in self:
            category.donor_count = len(category.donor_ids)
    
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Category name must be unique!'),
    ]
