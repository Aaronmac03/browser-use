"""
Hybrid Browser-Use Workflow Examples

This package contains example workflows demonstrating the hybrid architecture:
- Cloud planning for strategic intelligence
- Local execution for privacy preservation
- Real-world automation scenarios
- GTX 1660 Ti hardware optimization

Available Workflows:
- 01_hybrid_research.py: AI research and competitive analysis
- 02_account_automation.py: Social media and account management  
- 03_data_extraction.py: Privacy-first web scraping and analysis

All workflows preserve privacy by processing web content locally
while leveraging cloud intelligence for strategic planning.
"""

__version__ = "1.0.0"

# Workflow categories
RESEARCH_WORKFLOWS = [
	"hybrid_research",
]

ACCOUNT_WORKFLOWS = [
	"account_automation", 
]

DATA_WORKFLOWS = [
	"data_extraction",
]

ALL_WORKFLOWS = RESEARCH_WORKFLOWS + ACCOUNT_WORKFLOWS + DATA_WORKFLOWS