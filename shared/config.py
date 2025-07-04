from dataclasses import dataclass, field
from typing import List, Optional
import os

@dataclass
class BaseConfig:
    """Base configuration for cloud discovery."""
    output_directory: str = "output"
    output_format: str = "txt"  # json, csv, txt
    regions: Optional[List[str]] = field(default_factory=list)

    def __post_init__(self):
        # Create output directory if it doesn't exist
        os.makedirs(self.output_directory, exist_ok=True)
        # Validate output format
        if self.output_format not in ["json", "csv", "txt"]:
            raise ValueError(f"Invalid output format: {self.output_format}. Supported: json, csv, txt")

    def validate(self) -> bool:
        if not self.output_directory:
            print("Error: Output directory is required")
            return False
        if self.output_format not in ["json", "csv", "txt"]:
            print(f"Error: Invalid output format '{self.output_format}'")
            return False
        return True


@dataclass
class DiscoveryConfig:
    """Configuration for multi-cloud discovery."""
    regions: List[str]
    output_directory: str
    output_format: str
    provider: str

    def __post_init__(self):
        # Create output directory if it doesn't exist
        os.makedirs(self.output_directory, exist_ok=True)
        # Validate output format
        if self.output_format not in ["json", "csv", "txt"]:
            raise ValueError(f"Invalid output format: {self.output_format}. Supported: json, csv, txt")

    def validate(self) -> bool:
        if not self.output_directory:
            print("Error: Output directory is required")
            return False
        if self.output_format not in ["json", "csv", "txt"]:
            print(f"Error: Invalid output format '{self.output_format}'")
            return False
        return True 