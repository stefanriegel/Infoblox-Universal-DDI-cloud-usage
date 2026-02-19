"""
Constants and configuration values for Infoblox Universal DDI Resource Counter.
"""

# Token calculation constants
DDI_OBJECTS_PER_TOKEN = 25
ACTIVE_IPS_PER_TOKEN = 13
ASSETS_PER_TOKEN = 3
TOKEN_PACK_SIZE = 1000

# Supported cloud providers
SUPPORTED_PROVIDERS = ["aws", "azure", "gcp", "multicloud"]

# Default configuration values
DEFAULT_WORKERS = 8
DEFAULT_OUTPUT_FORMAT = "txt"
DEFAULT_OUTPUT_DIRECTORY = "output"

# Supported output formats
SUPPORTED_OUTPUT_FORMATS = ["json", "csv", "txt"]

# Resource type mappings for different providers
DDI_RESOURCE_TYPES = {
    "aws": [
        "subnet",
        "vpc",
        "route53-zone",
        "route53-record",
        "dhcp-option-set",
        "eks-cluster",
    ],
    "azure": [
        "dns-zone",
        "dns-record",
        "subnet",
        "vnet",
        "aks-cluster",
    ],
    "gcp": [
        "subnet",
        "vpc-network",
        "dns-zone",
        "dns-record",
        "gke-cluster",
    ],
    "multicloud": [
        "subnet",
        "vpc",
        "vpc-network",
        "vnet",
        "route53-zone",
        "route53-record",
        "dns-zone",
        "dns-record",
        "dhcp-option-set",
        "eks-cluster",
        "gke-cluster",
        "aks-cluster",
    ],
}

ASSET_RESOURCE_TYPES = {
    "aws": [
        "ec2-instance",
        "application-load-balancer",
        "network-load-balancer",
        "classic-load-balancer",
    ],
    "azure": [
        "vm",
        "vmss-instance",
        "gateway",
        "endpoint",
        "firewall",
        "switch",
        "router",
        "server",
        "load-balancer",
    ],
    "gcp": [
        "compute-instance",
    ],
    "multicloud": [
        "ec2-instance",
        "vm",
        "vmss-instance",
        "compute-instance",
        "application-load-balancer",
        "network-load-balancer",
        "classic-load-balancer",
        "gateway",
        "endpoint",
        "firewall",
        "switch",
        "router",
        "server",
        "load-balancer",
    ],
}

# IP address detail keys for extraction
IP_DETAIL_KEYS = [
    "ip",
    "private_ip",
    "public_ip",
    "private_ips",
    "public_ips",
    "ipv6_ip",
    "ipv6_ips",
    "ip_address",  # common for allocated/static IP resources
    "elastic_ip",
    "elastic_ips",
]

# Managed service indicators for different providers (tag key prefixes)
MANAGED_SERVICE_INDICATORS = {
    "aws": ["aws:ecs:", "aws:eks:", "eks.amazonaws.com/", "lambda:", "aws:lambda:", "aws-managed"],
    "azure": ["aks-managed-", "k8s-azure-", "ms-resource-usage:", "azure-managed"],
    "gcp": [
        "goog-managed-by",
        "managed-by",
        "google-managed",
        "gke-managed",
        "cloud-run",
        "cloud-functions",
    ],
}

# Error messages
ERROR_MESSAGES = {
    "unsupported_provider": "Unsupported provider: {provider}. Must be one of {supported}",
    "invalid_output_format": "Invalid output format '{format}'. Supported formats: {supported}",
    "missing_output_directory": "Output directory is required",
    "credentials_not_found": "Credentials not found. Please configure your cloud provider credentials.",
    "discovery_failed": "Discovery failed: {error}",
    "import_error": "Error importing {module} module: {error}",
    "installation_required": "Please ensure you have installed the required dependencies: "
    "pip install -r {provider}/requirements.txt",
}

# Logging configuration
LOGGING_CONFIG = {
    "level": "WARNING",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "suppress_modules": ["boto3", "botocore", "urllib3"],
}

# File naming patterns
FILE_PATTERNS = {
    "native_objects": "{provider}_native_objects_{timestamp}.{format}",
    "management_token_calculation": "{provider}_management_token_calculation_{timestamp}.{format}",
    "management_token_free": "{provider}_management_token_free_{timestamp}.{format}",
}

# AWS specific constants
AWS_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-central-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "sa-east-1",
]

# Azure specific constants
AZURE_REGIONS = [
    "eastus",
    "eastus2",
    "southcentralus",
    "westus2",
    "westus3",
    "canadacentral",
    "northeurope",
    "westeurope",
    "uksouth",
    "ukwest",
    "eastasia",
    "southeastasia",
]

# GCP specific constants
GCP_REGIONS = [
    "us-central1",
    "us-east1",
    "us-west1",
    "europe-west1",
    "asia-east1",
    "asia-southeast1",
]
