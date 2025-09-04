#!/usr/bin/env python3
"""
Error monitoring and alerting system for hybrid orchestrator.
Provides comprehensive error tracking, performance monitoring, and alerting capabilities.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
	"""Alert severity levels."""
	INFO = "info"
	WARNING = "warning"
	ERROR = "error"
	CRITICAL = "critical"


class ErrorCategory(Enum):
	"""Categories of errors for classification."""
	CONNECTION = "connection"
	TIMEOUT = "timeout"
	LLM_FAILURE = "llm_failure"
	BROWSER_ERROR = "browser_error"
	CLOUD_SERVICE = "cloud_service"
	RECOVERY_FAILURE = "recovery_failure"
	PERFORMANCE = "performance"
	UNKNOWN = "unknown"


@dataclass
class ErrorEvent:
	"""Individual error event record."""
	timestamp: datetime
	category: ErrorCategory
	severity: AlertLevel
	message: str
	context: Dict[str, Any]
	step_number: Optional[int] = None
	recovery_attempted: bool = False
	resolved: bool = False
	resolution_time: Optional[datetime] = None


@dataclass
class PerformanceMetrics:
	"""Performance metrics for monitoring."""
	total_tasks: int = 0
	successful_tasks: int = 0
	failed_tasks: int = 0
	total_steps: int = 0
	successful_steps: int = 0
	failed_steps: int = 0
	recovery_attempts: int = 0
	successful_recoveries: int = 0
	avg_task_time: float = 0.0
	avg_step_time: float = 0.0
	cloud_api_calls: int = 0
	local_processing_ratio: float = 1.0
	
	def get_task_success_rate(self) -> float:
		"""Get task-level success rate."""
		if self.total_tasks == 0:
			return 1.0
		return self.successful_tasks / self.total_tasks
	
	def get_step_success_rate(self) -> float:
		"""Get step-level success rate."""
		if self.total_steps == 0:
			return 1.0
		return self.successful_steps / self.total_steps
	
	def get_recovery_success_rate(self) -> float:
		"""Get recovery success rate."""
		if self.recovery_attempts == 0:
			return 1.0
		return self.successful_recoveries / self.recovery_attempts


@dataclass
class MonitoringConfig:
	"""Configuration for error monitoring."""
	# Error tracking
	max_error_history: int = 1000
	error_aggregation_window: int = 300  # seconds
	
	# Performance thresholds
	min_task_success_rate: float = 0.8
	min_step_success_rate: float = 0.85
	max_avg_step_time: float = 120.0  # seconds
	max_recovery_rate: float = 0.3  # 30% recovery rate is concerning
	min_local_processing_ratio: float = 0.9  # 90% local processing target
	
	# Alerting
	enable_alerts: bool = True
	alert_cooldown: int = 300  # seconds between similar alerts
	log_file: Optional[Path] = None
	
	# Persistence  
	state_file: Optional[Path] = field(default_factory=lambda: Path("monitoring_state.json"))
	auto_save_interval: int = 60  # seconds


class ErrorMonitor:
	"""Comprehensive error monitoring and alerting system."""
	
	def __init__(self, config: MonitoringConfig = None):
		self.config = config or MonitoringConfig()
		
		# Error tracking
		self.error_history: deque[ErrorEvent] = deque(maxlen=self.config.max_error_history)
		self.error_counts: Dict[ErrorCategory, int] = defaultdict(int)
		self.recent_errors: Dict[ErrorCategory, datetime] = {}
		
		# Performance tracking
		self.metrics = PerformanceMetrics()
		self.task_times: deque[float] = deque(maxlen=100)
		self.step_times: deque[float] = deque(maxlen=500)
		
		# Alerting
		self.alert_handlers: List[Callable] = []
		self.last_alerts: Dict[str, datetime] = {}
		
		# State management
		self.last_save_time = time.time()
		self._load_state()
		
		logger.info("[MONITOR] Error monitoring system initialized")
	
	def record_error(
		self,
		category: ErrorCategory,
		message: str,
		severity: AlertLevel = AlertLevel.ERROR,
		context: Dict[str, Any] = None,
		step_number: Optional[int] = None
	) -> ErrorEvent:
		"""Record an error event."""
		event = ErrorEvent(
			timestamp=datetime.now(),
			category=category,
			severity=severity,
			message=message,
			context=context or {},
			step_number=step_number
		)
		
		self.error_history.append(event)
		self.error_counts[category] += 1
		self.recent_errors[category] = event.timestamp
		
		# Check for alerting conditions
		if self.config.enable_alerts:
			self._check_alert_conditions(event)
		
		logger.error(f"[ERROR] {category.value.upper()}: {message}")
		return event
	
	def record_recovery_attempt(self, error_event: ErrorEvent, success: bool):
		"""Record a recovery attempt for an error."""
		error_event.recovery_attempted = True
		self.metrics.recovery_attempts += 1
		
		if success:
			error_event.resolved = True
			error_event.resolution_time = datetime.now()
			self.metrics.successful_recoveries += 1
			logger.info(f"[RECOVERY] Successfully recovered from {error_event.category.value}")
		else:
			logger.warning(f"[RECOVERY] Failed to recover from {error_event.category.value}")
	
	def record_task_start(self):
		"""Record the start of a task."""
		self.metrics.total_tasks += 1
	
	def record_task_completion(self, success: bool, duration: float):
		"""Record task completion."""
		if success:
			self.metrics.successful_tasks += 1
		else:
			self.metrics.failed_tasks += 1
		
		self.task_times.append(duration)
		self._update_avg_times()
		
		# Auto-save state periodically
		if time.time() - self.last_save_time > self.config.auto_save_interval:
			self._save_state()
	
	def record_step_completion(self, success: bool, duration: float):
		"""Record step completion."""
		self.metrics.total_steps += 1
		
		if success:
			self.metrics.successful_steps += 1
		else:
			self.metrics.failed_steps += 1
		
		self.step_times.append(duration)
		self._update_avg_times()
	
	def record_cloud_api_call(self):
		"""Record a cloud API call."""
		self.metrics.cloud_api_calls += 1
		# Update local processing ratio
		total_operations = self.metrics.total_steps + self.metrics.cloud_api_calls
		if total_operations > 0:
			self.metrics.local_processing_ratio = self.metrics.total_steps / total_operations
	
	def get_error_summary(self, time_window: int = 3600) -> Dict[str, Any]:
		"""Get error summary for the specified time window (seconds)."""
		cutoff_time = datetime.now() - timedelta(seconds=time_window)
		recent_errors = [e for e in self.error_history if e.timestamp > cutoff_time]
		
		category_counts = defaultdict(int)
		severity_counts = defaultdict(int)
		unresolved_count = 0
		
		for error in recent_errors:
			category_counts[error.category.value] += 1
			severity_counts[error.severity.value] += 1
			if not error.resolved:
				unresolved_count += 1
		
		return {
			'time_window_hours': time_window / 3600,
			'total_errors': len(recent_errors),
			'unresolved_errors': unresolved_count,
			'errors_by_category': dict(category_counts),
			'errors_by_severity': dict(severity_counts),
			'recovery_rate': len([e for e in recent_errors if e.recovery_attempted and e.resolved]) / max(len(recent_errors), 1)
		}
	
	def get_performance_report(self) -> Dict[str, Any]:
		"""Get comprehensive performance report."""
		return {
			'metrics': {
				'task_success_rate': self.metrics.get_task_success_rate(),
				'step_success_rate': self.metrics.get_step_success_rate(),
				'recovery_success_rate': self.metrics.get_recovery_success_rate(),
				'avg_task_time': self.metrics.avg_task_time,
				'avg_step_time': self.metrics.avg_step_time,
				'local_processing_ratio': self.metrics.local_processing_ratio,
				'total_tasks': self.metrics.total_tasks,
				'total_steps': self.metrics.total_steps,
				'cloud_api_calls': self.metrics.cloud_api_calls
			},
			'thresholds': {
				'min_task_success_rate': self.config.min_task_success_rate,
				'min_step_success_rate': self.config.min_step_success_rate,
				'max_avg_step_time': self.config.max_avg_step_time,
				'min_local_processing_ratio': self.config.min_local_processing_ratio
			},
			'alerts': self._check_performance_thresholds()
		}
	
	def add_alert_handler(self, handler: Callable[[AlertLevel, str, Dict], None]):
		"""Add a custom alert handler."""
		self.alert_handlers.append(handler)
	
	def get_health_status(self) -> Dict[str, Any]:
		"""Get overall system health status."""
		performance_alerts = self._check_performance_thresholds()
		recent_errors = self.get_error_summary(900)  # Last 15 minutes
		
		# Determine overall health
		if any(alert['level'] == AlertLevel.CRITICAL for alert in performance_alerts):
			health = "CRITICAL"
		elif any(alert['level'] == AlertLevel.ERROR for alert in performance_alerts):
			health = "UNHEALTHY"
		elif any(alert['level'] == AlertLevel.WARNING for alert in performance_alerts) or recent_errors['total_errors'] > 5:
			health = "DEGRADED"
		else:
			health = "HEALTHY"
		
		return {
			'overall_health': health,
			'recent_error_count': recent_errors['total_errors'],
			'task_success_rate': self.metrics.get_task_success_rate(),
			'step_success_rate': self.metrics.get_step_success_rate(),
			'local_processing_ratio': self.metrics.local_processing_ratio,
			'uptime_tasks': self.metrics.total_tasks,
			'active_alerts': len(performance_alerts)
		}
	
	def _update_avg_times(self):
		"""Update average timing metrics."""
		if self.task_times:
			self.metrics.avg_task_time = sum(self.task_times) / len(self.task_times)
		if self.step_times:
			self.metrics.avg_step_time = sum(self.step_times) / len(self.step_times)
	
	def _check_alert_conditions(self, event: ErrorEvent):
		"""Check if an alert should be triggered."""
		alert_key = f"{event.category.value}_{event.severity.value}"
		
		# Check cooldown
		if alert_key in self.last_alerts:
			if (datetime.now() - self.last_alerts[alert_key]).seconds < self.config.alert_cooldown:
				return
		
		# Trigger alert
		self._trigger_alert(event.severity, f"{event.category.value.title()} Error", {
			'message': event.message,
			'context': event.context,
			'step_number': event.step_number
		})
		
		self.last_alerts[alert_key] = datetime.now()
	
	def _check_performance_thresholds(self) -> List[Dict[str, Any]]:
		"""Check performance thresholds and return alerts."""
		alerts = []
		
		# Task success rate
		task_success_rate = self.metrics.get_task_success_rate()
		if task_success_rate < self.config.min_task_success_rate:
			alerts.append({
				'level': AlertLevel.ERROR,
				'metric': 'task_success_rate',
				'value': task_success_rate,
				'threshold': self.config.min_task_success_rate,
				'message': f"Task success rate ({task_success_rate:.1%}) below threshold ({self.config.min_task_success_rate:.1%})"
			})
		
		# Step success rate
		step_success_rate = self.metrics.get_step_success_rate()
		if step_success_rate < self.config.min_step_success_rate:
			alerts.append({
				'level': AlertLevel.ERROR,
				'metric': 'step_success_rate',
				'value': step_success_rate,
				'threshold': self.config.min_step_success_rate,
				'message': f"Step success rate ({step_success_rate:.1%}) below threshold ({self.config.min_step_success_rate:.1%})"
			})
		
		# Average step time
		if self.metrics.avg_step_time > self.config.max_avg_step_time:
			alerts.append({
				'level': AlertLevel.WARNING,
				'metric': 'avg_step_time',
				'value': self.metrics.avg_step_time,
				'threshold': self.config.max_avg_step_time,
				'message': f"Average step time ({self.metrics.avg_step_time:.1f}s) exceeds threshold ({self.config.max_avg_step_time:.1f}s)"
			})
		
		# Recovery rate
		recovery_rate = self.metrics.recovery_attempts / max(self.metrics.total_steps, 1)
		if recovery_rate > self.config.max_recovery_rate:
			alerts.append({
				'level': AlertLevel.WARNING,
				'metric': 'recovery_rate',
				'value': recovery_rate,
				'threshold': self.config.max_recovery_rate,
				'message': f"Recovery rate ({recovery_rate:.1%}) exceeds threshold ({self.config.max_recovery_rate:.1%})"
			})
		
		# Local processing ratio
		if self.metrics.local_processing_ratio < self.config.min_local_processing_ratio:
			alerts.append({
				'level': AlertLevel.WARNING,
				'metric': 'local_processing_ratio',
				'value': self.metrics.local_processing_ratio,
				'threshold': self.config.min_local_processing_ratio,
				'message': f"Local processing ratio ({self.metrics.local_processing_ratio:.1%}) below target ({self.config.min_local_processing_ratio:.1%})"
			})
		
		return alerts
	
	def _trigger_alert(self, level: AlertLevel, title: str, context: Dict[str, Any]):
		"""Trigger an alert through all configured handlers."""
		for handler in self.alert_handlers:
			try:
				handler(level, title, context)
			except Exception as e:
				logger.error(f"[ALERT] Alert handler failed: {e}")
	
	def _save_state(self):
		"""Save monitoring state to disk."""
		if not self.config.state_file:
			return
		
		try:
			state = {
				'metrics': {
					'total_tasks': self.metrics.total_tasks,
					'successful_tasks': self.metrics.successful_tasks,
					'failed_tasks': self.metrics.failed_tasks,
					'total_steps': self.metrics.total_steps,
					'successful_steps': self.metrics.successful_steps,
					'failed_steps': self.metrics.failed_steps,
					'recovery_attempts': self.metrics.recovery_attempts,
					'successful_recoveries': self.metrics.successful_recoveries,
					'cloud_api_calls': self.metrics.cloud_api_calls,
				},
				'error_counts': dict(self.error_counts),
				'last_save': datetime.now().isoformat()
			}
			
			with open(self.config.state_file, 'w') as f:
				json.dump(state, f, indent=2)
			
			self.last_save_time = time.time()
			logger.debug("[MONITOR] State saved successfully")
		except Exception as e:
			logger.error(f"[MONITOR] Failed to save state: {e}")
	
	def _load_state(self):
		"""Load monitoring state from disk."""
		if not self.config.state_file or not self.config.state_file.exists():
			return
		
		try:
			with open(self.config.state_file, 'r') as f:
				state = json.load(f)
			
			# Restore metrics
			metrics_data = state.get('metrics', {})
			for key, value in metrics_data.items():
				if hasattr(self.metrics, key):
					setattr(self.metrics, key, value)
			
			# Restore error counts
			error_counts_data = state.get('error_counts', {})
			for category_str, count in error_counts_data.items():
				try:
					category = ErrorCategory(category_str)
					self.error_counts[category] = count
				except ValueError:
					pass  # Skip unknown categories
			
			logger.info("[MONITOR] State loaded successfully")
		except Exception as e:
			logger.warning(f"[MONITOR] Failed to load state: {e}")


# Default alert handlers
def console_alert_handler(level: AlertLevel, title: str, context: Dict[str, Any]):
	"""Simple console alert handler."""
	timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	print(f"[{timestamp}] {level.value.upper()}: {title}")
	if context.get('message'):
		print(f"  Message: {context['message']}")
	if context.get('step_number'):
		print(f"  Step: {context['step_number']}")


def file_alert_handler(log_file: Path):
	"""Create a file-based alert handler."""
	def handler(level: AlertLevel, title: str, context: Dict[str, Any]):
		timestamp = datetime.now().isoformat()
		log_entry = {
			'timestamp': timestamp,
			'level': level.value,
			'title': title,
			'context': context
		}
		
		try:
			with open(log_file, 'a') as f:
				f.write(json.dumps(log_entry) + '\n')
		except Exception as e:
			logger.error(f"Failed to write alert to file: {e}")
	
	return handler