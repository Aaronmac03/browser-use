"""Test specific navigation case."""

import logging
from models.enhanced_model_router import EnhancedModelRouter, EnhancedTaskRequirements
from config.enhanced_models import EnhancedModelConfigManager
from models.cloud_handler import CloudModelManager, BudgetManager, ResponseCache

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

config_manager = EnhancedModelConfigManager()
budget_manager = BudgetManager(daily_limit=10.0, monthly_limit=50.0)
cache = ResponseCache(max_age_hours=24)

cloud_manager = CloudModelManager(
    openai_api_key="test",  # Mock key
    anthropic_api_key=None,
    budget_manager=budget_manager,
    cache=cache
)

router = EnhancedModelRouter(
    model_config_manager=config_manager,
    local_handler=None,
    cloud_manager=cloud_manager,
    serper_api=None
)

test_case = "Navigate to Google and search for 'python tutorials'"
print(f"Testing: {test_case}")

task_req = EnhancedTaskRequirements(
    task_description=test_case,
    has_dom_state=False
)

result = router._should_use_planner(task_req)
print(f"Planning needed: {result}")
print(f"Should be: False (simple navigation + search)")