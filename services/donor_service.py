# -*- coding: utf-8 -*-

from odoo import models, api, _


class DonorService(models.AbstractModel):
    """Service for Donor business operations."""
    
    _name = 'ngo.grant.donor.service'
    _description = 'NGO Donor Service'
    
    @api.model
    def get_donor_statistics(self, donor_id):
        """Get comprehensive donor statistics."""
        donor = self.env['ngo.grant.donor'].browse(donor_id)
        
        return {
            'donor_code': donor.donor_code,
            'donor_type': donor.donor_type,
            'donor_status': donor.donor_status,
            'grant_count': donor.grant_count,
            'active_grant_count': donor.active_grant_count,
            'total_funding': donor.total_funding,
            'active_project_count': donor.active_project_count,
            'due_diligence_completed': donor.due_diligence_completed,
        }
    
    @api.model
    def get_donor_grants(self, donor_id):
        """Get all grants for a donor."""
        donor = self.env['ngo.grant.donor'].browse(donor_id)
        return donor.donor_line_ids.mapped('grant_id')
    
    @api.model
    def validate_donor_for_grant(self, donor_id):
        """Validate that a donor can participate in a grant."""
        donor = self.env['ngo.grant.donor'].browse(donor_id)
        
        if donor.donor_status == 'blacklisted':
            raise ValidationError(_('Blacklisted donors cannot participate in grants.'))
        
        if donor.donor_status == 'suspended':
            raise ValidationError(_('Suspended donors cannot participate in grants.'))
        
        if not donor.due_diligence_completed:
            raise ValidationError(_('Due diligence must be completed before donor can participate in grants.'))
        
        return True
    
    @api.model
    def get_donor_contacts(self, donor_id, role=None):
        """Get donor contacts, optionally filtered by role."""
        donor = self.env['ngo.grant.donor'].browse(donor_id)
        domain = [('donor_id', '=', donor_id)]
        if role:
            domain.append(('contact_role', '=', role))
        return self.env['ngo.grant.contact'].search(domain)
    
    @api.model
    def get_primary_contact(self, donor_id):
        """Get primary contact for a donor."""
        donor = self.env['ngo.grant.donor'].browse(donor_id)
        return donor.contact_ids.filtered(lambda c: c.primary_contact)[:1]
