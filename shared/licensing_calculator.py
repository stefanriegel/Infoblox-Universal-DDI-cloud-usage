#!/usr/bin/env python3
"""
Universal DDI Licensing Calculator

Calculates Infoblox Universal DDI licensing requirements based on discovered cloud resources.
Uses official Infoblox Universal DDI licensing metrics from the documentation.
"""

from datetime import datetime
from typing import Dict, List, Tuple, Any
import json
import csv
import os
from shared.constants import AWS_REGIONS, AZURE_REGIONS, GCP_REGIONS


class UniversalDDILicensingCalculator:
    """Calculate Universal DDI licensing requirements from discovered resources."""
    
    # Official Infoblox Universal DDI licensing ratios (Native Objects)
    DDI_OBJECTS_PER_TOKEN = 25      # DDI Objects per Management Token
    ACTIVE_IPS_PER_TOKEN = 13       # Active IP Addresses per Management Token  
    ASSETS_PER_TOKEN = 3            # Managed Assets per Management Token
    
    def __init__(self):
        """Initialize the licensing calculator."""
        self.results = {}
        self.current_provider: str | None = None
    
    def calculate_from_discovery_results(self, native_objects: List[Dict], provider: str | None = None) -> Dict[str, Any]:
        """
        Calculate licensing requirements from native discovery results.
        
        Args:
            native_objects: List of discovered resources from cloud providers
            provider: The active provider context (aws|azure|gcp) to preference mapping
            
        Returns:
            Dictionary with licensing calculations and recommendations
        """
        self.current_provider = (provider or '').lower() or None
        # Count DDI Objects (network infrastructure for DNS/DHCP/IPAM)
        ddi_objects = self._count_ddi_objects(native_objects)
        
        # Count Active IP Addresses (IPs assigned to running resources)
        active_ips = self._count_active_ips(native_objects)
        
        # Count Managed Assets (compute/network resources with IPs)
        managed_assets = self._count_managed_assets(native_objects)
        
        # Calculate required tokens
        tokens_for_ddi = max(1, (ddi_objects + self.DDI_OBJECTS_PER_TOKEN - 1) // self.DDI_OBJECTS_PER_TOKEN)
        tokens_for_ips = max(1, (active_ips + self.ACTIVE_IPS_PER_TOKEN - 1) // self.ACTIVE_IPS_PER_TOKEN)
        tokens_for_assets = max(1, (managed_assets + self.ASSETS_PER_TOKEN - 1) // self.ASSETS_PER_TOKEN)
        
        # Total management tokens needed (sum of all three categories)
        total_management_tokens = tokens_for_ddi + tokens_for_ips + tokens_for_assets
        
        # Generate provider breakdown
        provider_breakdown = self._get_provider_breakdown(native_objects)
        
        result = {
            "calculation_timestamp": datetime.now().isoformat(),
            "licensing_basis": "Infoblox Universal DDI Native Objects (25/13/3 per token)",
            "counts": {
                "ddi_objects": ddi_objects,
                "active_ip_addresses": active_ips,
                "managed_assets": managed_assets,
                "total_objects": len(native_objects)
            },
            "token_requirements": {
                "ddi_objects_tokens": tokens_for_ddi,
                "active_ips_tokens": tokens_for_ips, 
                "managed_assets_tokens": tokens_for_assets,
                "total_management_tokens": total_management_tokens
            },
            "provider_breakdown": provider_breakdown,
            "sizing_ratios": {
                "ddi_objects_per_token": self.DDI_OBJECTS_PER_TOKEN,
                "active_ips_per_token": self.ACTIVE_IPS_PER_TOKEN,
                "assets_per_token": self.ASSETS_PER_TOKEN
            }
        }
        
        self.results = result
        return result
    
    def _count_ddi_objects(self, resources: List[Dict]) -> int:
        """Count DDI Objects (DNS/DHCP/IPAM infrastructure)."""
        ddi_resource_types = {
            # AWS DDI Objects
            'vpc', 'subnet', 'route53-zone', 'route53-record',
            # Azure DDI Objects  
            'vnet', 'dns-zone', 'dns-record', 'dhcp-range', 'ipam-block', 'ipam-space',
            'host-record', 'ddns-record', 'address-block', 'view', 'zone',
            'dtc-lbdn', 'dtc-server', 'dtc-pool', 'dtc-topology-rule', 'dtc-health-check',
            'dhcp-exclusion-range', 'dhcp-filter-rule', 'dhcp-option', 'ddns-zone',
            # GCP DDI Objects
            'vpc-network', 'dns-zone', 'dns-record'
        }
        
        return len([r for r in resources if r.get('resource_type') in ddi_resource_types])
    
    def _count_active_ips(self, resources: List[Dict]) -> int:
        """Count Active IP Addresses.
        Definition: An IP address "seen" on the network and IP addresses reserved or used for DNS and DHCP.
        This includes discovered/attached IPs, DHCP lease IPs, fixed/reserved addresses, and DNS-used IPs.
        """
        ip_set = set()
        
        # Helper to add IP(s) from value if str or list[str]
        def _add_ips(val):
            if not val:
                return
            if isinstance(val, str):
                ip_set.add(val)
            elif isinstance(val, list):
                for v in val:
                    if v:
                        ip_set.add(v)
        
        for resource in resources:
            details = resource.get('details', {})
            
            # Extract IPs from common fields (attached/seen on the network)
            for ip_field in ['ip', 'private_ip', 'public_ip']:
                _add_ips(details.get(ip_field))
            
            # Extract IPs from common list fields (multiple interfaces/addresses)
            for ip_list_field in ['private_ips', 'public_ips']:
                _add_ips(details.get(ip_list_field))
            
            # Include reserved/lease/fixed IPs when present (DNS/DHCP usage)
            for key in [
                'reserved_ips', 'reservation_ips', 'fixed_ips', 'fixed_addresses',
                'dhcp_lease_ips', 'lease_ips', 'leases',
                'elastic_ip', 'elastic_ips',  # AWS reserved/static addresses
                'dns_record_ips', 'a_record_ips', 'aaaa_record_ips'  # DNS-used IPs if provided
            ]:
                _add_ips(details.get(key))
        
        return len(ip_set)
    
    def _count_managed_assets(self, resources: List[Dict]) -> int:
        """Count Managed Assets (compute/network resources with IPs)."""
        asset_resource_types = {
            # AWS Assets
            'ec2-instance', 'application-load-balancer', 'network-load-balancer', 'classic-load-balancer',
            # Azure Assets
            'vm', 'load_balancer', 'gateway', 'endpoint', 'firewall', 'switch', 'router', 'server',
            # GCP Assets
            'compute-instance'
        }
        
        # Count assets that have IP addresses (as per Infoblox licensing rules)
        asset_count = 0
        for resource in resources:
            if resource.get('resource_type') in asset_resource_types:
                # Check if asset has at least one IP address
                details = resource.get('details', {})
                has_ip = False
                
                # Check for IP fields
                for ip_field in ['ip', 'private_ip', 'public_ip', 'private_ips', 'public_ips']:
                    if details.get(ip_field):
                        has_ip = True
                        break
                
                if has_ip:
                    asset_count += 1
        
        return asset_count
    
    def _get_provider_breakdown(self, resources: List[Dict]) -> Dict[str, Dict[str, int]]:
        """Get breakdown of counts by cloud provider."""
        providers = {}
        
        for resource in resources:
            # Determine provider from resource details or region
            provider = self._determine_provider(resource)
            
            if provider not in providers:
                providers[provider] = {
                    'ddi_objects': 0,
                    'active_ips': 0, 
                    'managed_assets': 0,
                    'total_objects': 0
                }
            
            providers[provider]['total_objects'] += 1
            
            # Categorize the resource
            resource_type = resource.get('resource_type', '')
            
            if self._is_ddi_object(resource_type):
                providers[provider]['ddi_objects'] += 1
            elif self._is_managed_asset(resource_type):
                # Only count if it has IP addresses
                details = resource.get('details', {})
                if self._has_ip_addresses(details):
                    providers[provider]['managed_assets'] += 1
        
        # Count unique IPs per provider
        for provider in providers:
            provider_resources = [r for r in resources if self._determine_provider(r) == provider]
            providers[provider]['active_ips'] = self._count_active_ips(provider_resources)
        
        return providers
    
    def _determine_provider(self, resource: Dict) -> str:
        """Determine cloud provider from resource by region or resource_type, preferring current provider when ambiguous."""
        region = (resource.get('region') or '').lower()
        rtype = (resource.get('resource_type') or '').lower()

        # Region-based mapping using known region lists
        if region in [r.lower() for r in AWS_REGIONS]:
            return 'aws'
        if region in [r.lower() for r in AZURE_REGIONS]:
            return 'azure'
        if region in [r.lower() for r in GCP_REGIONS]:
            return 'gcp'

        # Type-based mapping sets
        aws_types = {'vpc', 'subnet', 'route53-zone', 'route53-record'}
        azure_types = {
            'vm','vnet','subnet','dns-zone','dns-record','endpoint','switch','gateway','router',
            'dhcp-range','ipam-block','ipam-space','host-record','ddns-record','address-block','view','zone'
        }
        gcp_types = {'compute-instance','vpc-network','dns-zone','dns-record'}

        # Prefer current provider on overlap
        cp = (self.current_provider or '').lower()
        if cp == 'aws' and rtype in aws_types:
            return 'aws'
        if cp == 'azure' and rtype in azure_types:
            return 'azure'
        if cp == 'gcp' and rtype in gcp_types:
            return 'gcp'

        # Otherwise choose by type order: gcp first (to avoid misclassifying 'dns-zone'), then azure, then aws
        if rtype in gcp_types:
            return 'gcp'
        if rtype in azure_types:
            return 'azure'
        if rtype in aws_types:
            return 'aws'

        # Fallback on patterns
        if 'route53' in rtype or rtype.startswith('ec2-'):
            return 'aws'
        if rtype in ('managedzone','recordset'):
            return 'gcp'

        # Region 'global' could belong to any; prefer current provider if set
        if region == 'global' and cp in {'aws','azure','gcp'}:
            return cp

        return 'unknown'
    
    def _is_ddi_object(self, resource_type: str) -> bool:
        """Check if resource type is a DDI object."""
        ddi_types = {
            'vpc', 'subnet', 'route53-zone', 'route53-record', 'vnet', 'dns-zone', 'dns-record',
            'dhcp-range', 'ipam-block', 'ipam-space', 'vpc-network'
        }
        return resource_type in ddi_types
    
    def _is_managed_asset(self, resource_type: str) -> bool:
        """Check if resource type is a managed asset."""
        asset_types = {
            'ec2-instance', 'application-load-balancer', 'network-load-balancer', 'classic-load-balancer',
            'vm', 'load_balancer', 'gateway', 'compute-instance'
        }
        return resource_type in asset_types
    
    def _has_ip_addresses(self, details: Dict) -> bool:
        """Check if resource details contain IP addresses."""
        ip_fields = ['ip', 'private_ip', 'public_ip', 'private_ips', 'public_ips']
        return any(details.get(field) for field in ip_fields)
    
    def export_csv(self, output_file: str, provider: str | None = None) -> str:
        """Export licensing calculations to CSV format for Sales Engineers (active provider only)."""
        if not self.results:
            raise ValueError("No calculation results available. Run calculate_from_discovery_results first.")
        
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header
            writer.writerow(['Infoblox Universal DDI Licensing Calculator'])
            writer.writerow(['Generated:', self.results['calculation_timestamp']])
            writer.writerow(['Basis:', self.results['licensing_basis']])
            writer.writerow([])
            
            # Summary
            writer.writerow(['LICENSING SUMMARY'])
            writer.writerow(['Metric', 'Count', 'Tokens Required', 'Per Token Ratio'])
            writer.writerow(['DDI Objects', self.results['counts']['ddi_objects'], 
                           self.results['token_requirements']['ddi_objects_tokens'], 
                           f"{self.DDI_OBJECTS_PER_TOKEN} objects/token"])
            writer.writerow(['Active IP Addresses', self.results['counts']['active_ip_addresses'],
                           self.results['token_requirements']['active_ips_tokens'],
                           f"{self.ACTIVE_IPS_PER_TOKEN} IPs/token"])
            writer.writerow(['Managed Assets', self.results['counts']['managed_assets'],
                           self.results['token_requirements']['managed_assets_tokens'],
                           f"{self.ASSETS_PER_TOKEN} assets/token"])
            writer.writerow(['TOTAL MANAGEMENT TOKENS', '', 
                           self.results['token_requirements']['total_management_tokens'], ''])
            writer.writerow([])
            
            # Provider breakdown (only active provider)
            writer.writerow(['PROVIDER BREAKDOWN'])
            writer.writerow(['Provider', 'DDI Objects', 'Active IPs', 'Managed Assets', 'Total Objects'])
            pb = self.results.get('provider_breakdown', {}) or {}
            key = (provider or self.current_provider or '').lower()
            if key and key in pb:
                counts = pb[key]
                writer.writerow([key.upper(), counts['ddi_objects'], counts['active_ips'],
                               counts['managed_assets'], counts['total_objects']])
            
        return output_file
    
    def export_text_summary(self, output_file: str, provider: str | None = None) -> str:
        """Export a text summary for Sales Engineers (only for the active provider)."""
        if not self.results:
            raise ValueError("No calculation results available. Run calculate_from_discovery_results first.")
        
        with open(output_file, 'w') as f:
            f.write("INFOBLOX UNIVERSAL DDI LICENSING CALCULATOR\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Generated: {self.results['calculation_timestamp']}\n")
            f.write(f"Basis: {self.results['licensing_basis']}\n\n")
            
            # Summary
            f.write("LICENSING REQUIREMENTS SUMMARY\n")
            f.write("-" * 30 + "\n")
            f.write(f"DDI Objects: {self.results['counts']['ddi_objects']:,} "
                   f"({self.results['token_requirements']['ddi_objects_tokens']} tokens required)\n")
            f.write(f"Active IP Addresses: {self.results['counts']['active_ip_addresses']:,} "
                   f"({self.results['token_requirements']['active_ips_tokens']} tokens required)\n")
            f.write(f"Managed Assets: {self.results['counts']['managed_assets']:,} "
                   f"({self.results['token_requirements']['managed_assets_tokens']} tokens required)\n")
            f.write(f"\nTOTAL MANAGEMENT TOKENS REQUIRED: {self.results['token_requirements']['total_management_tokens']}\n\n")
            
            # Provider breakdown (only active provider)
            f.write("CLOUD PROVIDER BREAKDOWN\n")
            f.write("-" * 25 + "\n")
            pb = self.results.get('provider_breakdown', {}) or {}
            key = (provider or self.current_provider or '').lower()
            if key and key in pb:
                counts = pb[key]
                f.write(f"{key.upper()}:\n")
                f.write(f"  DDI Objects: {counts['ddi_objects']:,}\n")
                f.write(f"  Active IPs: {counts['active_ips']:,}\n")
                f.write(f"  Managed Assets: {counts['managed_assets']:,}\n")
                f.write(f"  Total Objects: {counts['total_objects']:,}\n\n")
            
            # Ratios
            f.write("INFOBLOX UNIVERSAL DDI SIZING RATIOS (Native Objects)\n")
            f.write("-" * 45 + "\n")
            f.write(f"DDI Objects: {self.DDI_OBJECTS_PER_TOKEN} per Management Token\n")
            f.write(f"Active IPs: {self.ACTIVE_IPS_PER_TOKEN} per Management Token\n")
            f.write(f"Managed Assets: {self.ASSETS_PER_TOKEN} per Management Token\n")
            
        return output_file

    def export_estimator_csv(self, output_file: str) -> str:
        """Export only Yellow-cell fields expected by the sizing Excel (flat CSV).
        Columns:
          - ddi_objects
          - active_ip_addresses
          - managed_assets
          - tokens_ddi_objects
          - tokens_active_ips
          - tokens_managed_assets
          - tokens_total
        """
        if not self.results:
            raise ValueError("No calculation results available. Run calculate_from_discovery_results first.")
        
        counts = self.results['counts']
        tokens = self.results['token_requirements']
        
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'ddi_objects',
                'active_ip_addresses',
                'managed_assets',
                'tokens_ddi_objects',
                'tokens_active_ips',
                'tokens_managed_assets',
                'tokens_total'
            ])
            writer.writerow([
                counts['ddi_objects'],
                counts['active_ip_addresses'],
                counts['managed_assets'],
                tokens['ddi_objects_tokens'],
                tokens['active_ips_tokens'],
                tokens['managed_assets_tokens'],
                tokens['total_management_tokens']
            ])
        return output_file

    def export_proof_manifest(
        self,
        output_file: str,
        provider: str,
        scope: dict,
        regions: list,
        native_objects: List[Dict]
    ) -> str:
        """Export an auditable JSON manifest for future sizing reviews.
        Includes: scope (accounts/subscriptions/projects), regions, ratios and source, breakdowns,
        and a SHA-256 hash over the discovered object set and over this manifest.
        """
        if not self.results:
            raise ValueError("No calculation results available. Run calculate_from_discovery_results first.")
        import hashlib, json as _json

        # Minimal resource projection for hashing to keep stable
        def project(r: Dict) -> Dict:
            d = r.get('details', {}) or {}
            # only keep likely-relevant IP fields as evidence
            ip_fields = {
                k: d.get(k) for k in (
                    'ip','private_ip','public_ip','private_ips','public_ips',
                    'reserved_ips','reservation_ips','fixed_ips','fixed_addresses',
                    'dhcp_lease_ips','lease_ips','leases','elastic_ip','elastic_ips') if k in d
            }
            return {
                'resource_id': r.get('resource_id'),
                'resource_type': r.get('resource_type'),
                'region': r.get('region'),
                'name': r.get('name'),
                'state': r.get('state'),
                'requires_management_token': r.get('requires_management_token'),
                'ip_evidence': ip_fields,
            }

        projected = [project(r) for r in native_objects]
        canonical = _json.dumps(projected, sort_keys=True, separators=(',', ':'))
        resources_sha256 = hashlib.sha256(canonical.encode('utf-8')).hexdigest()

        # Breakdown by resource_type counts
        by_type = {}
        for r in native_objects:
            t = r.get('resource_type','unknown')
            by_type[t] = by_type.get(t,0) + 1

        # Filter provider breakdown to the selected provider only
        pb_all = self.results.get('provider_breakdown', {}) or {}
        pb_filtered = {}
        if provider in pb_all:
            pb_filtered[provider] = pb_all.get(provider, {})

        manifest = {
            'generated_at': self.results.get('calculation_timestamp'),
            'provider': provider,
            'scope': scope or {},
            'regions': regions or [],
            'licensing_basis': self.results.get('licensing_basis'),
            'ratios': {
                'ddi_objects_per_token': self.DDI_OBJECTS_PER_TOKEN,
                'active_ips_per_token': self.ACTIVE_IPS_PER_TOKEN,
                'assets_per_token': self.ASSETS_PER_TOKEN
            },
            'counts': self.results.get('counts', {}),
            'token_requirements': self.results.get('token_requirements', {}),
            'breakdowns': {
                'provider_breakdown': pb_filtered,
            },
            'resources_summary': {
                'total_objects': len(native_objects),
                'by_type': by_type,
                'sample_resources': projected[:20]
            },
            'hashes': {
                'resources_sha256': resources_sha256
            }
        }

        # Write manifest
        with open(output_file, 'w') as f:
            _json.dump(manifest, f, indent=2)

        # Hash the manifest itself and append
        with open(output_file, 'rb') as f:
            manifest_sha256 = hashlib.sha256(f.read()).hexdigest()
        manifest_with_hash = dict(manifest, hashes=dict(manifest.get('hashes', {}), manifest_sha256=manifest_sha256))
        with open(output_file, 'w') as f:
            _json.dump(manifest_with_hash, f, indent=2)

        return output_file
