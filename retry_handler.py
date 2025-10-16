import asyncio
import logging
import time
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

class RetryHandler:
    """Handles retry logic with exponential backoff."""
    
    def __init__(self, max_retries: int = 1, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def retry_with_backoff(self, operation_name: str = "operation"):
        """
        Decorator for retrying operations with exponential backoff.
        
        Args:
            operation_name: Name of the operation for logging purposes
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                last_exception = None
                
                
                for attempt in range(self.max_retries + 1):
                    # 🔑 Check for shutdown on the instance (args[0] is usually `self`)
                    if len(args) > 0 and getattr(args[0], "_shutdown", False):
                        logger.info(f"{operation_name} aborted — client is shutting down")
                        raise Exception("Shutdown in progress")

                    try:
                        result = func(*args, **kwargs)
                        
                        if attempt > 0:
                            logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                        
                        return result
                    
                    except Exception as e:
                        last_exception = e
                        
                        if attempt < self.max_retries:
                            delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                            logger.warning(
                                f"{operation_name} failed on attempt {attempt + 1}/{self.max_retries + 1}. "
                                f"Retrying in {delay:.1f}s. Error: {str(e)}"
                            )
                            time.sleep(delay)
                        else:
                            logger.error(
                                f"{operation_name} failed after {self.max_retries + 1} attempts. "
                                f"Final error: {str(e)}"
                            )
                
                # If we reach here, all retries failed
                if last_exception:
                    raise last_exception
                else:
                    raise Exception(f"{operation_name} failed after all retries")
            
            return wrapper
        return decorator
    
    def execute_with_retry(
        self, 
        func: Callable, 
        operation_name: str = "operation",
        *args, 
        **kwargs
    ) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            operation_name: Name for logging
            *args, **kwargs: Arguments to pass to func
        
        Returns:
            Result of successful function execution
        
        Raises:
            Exception: The last exception if all retries fail
        """
        decorated_func = self.retry_with_backoff(operation_name)(func)
        return decorated_func(*args, **kwargs)

class CircuitBreaker:
    """Simple circuit breaker pattern implementation."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Returns:
            Result of function execution
        
        Raises:
            Exception: Circuit breaker open or function failed
        """
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
                logger.info("Circuit breaker moving to HALF_OPEN state")
            else:
                raise Exception(f"Circuit breaker OPEN. Last failure: {self.last_failure_time}")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            logger.info("Circuit breaker reset to CLOSED state")
    
    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")
    
    
    def reset(self):
        """Manually reset the circuit breaker to CLOSED state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'
        logger.info("Circuit breaker manually reset to CLOSED state")

# Global instances
default_retry_handler = RetryHandler()
eventstream_circuit_breaker = CircuitBreaker()
