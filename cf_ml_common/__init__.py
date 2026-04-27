"""
cf-ml-common: Shared infrastructure utilities for ClearFacts ML projects

This package provides reusable, domain-agnostic utilities for:
- Database connectivity (PostgreSQL, MySQL)
- AWS S3 operations
- Configuration parsing
- Password management (AWS Secrets Manager, SSM, environment variables)
- LLM token usage tracking
- Generic utilities (Struct, chunks, coalesce, JSON/gzip helpers)

This package contains application infrastructure code only. It does not include:
- Business logic
- Domain models
- Table schemas or queries
- Application-specific defaults
"""

__version__ = "0.1.0"

# LLM tracking is available via cf_ml_common.llm
# Other modules will be added as cf-ml-common is built out
