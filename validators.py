import json
import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class PayloadValidator:
    """Validates KoboToolbox webhook payloads."""
    
    REQUIRED_FIELDS = ['_id', '_submission_time', '_submitted_by']
    MAX_FIELD_LENGTH = 10000
    MAX_NESTED_DEPTH = 10
    
    @staticmethod
    def validate_kobo_payload(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate KoboToolbox payload structure and content.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if not isinstance(payload, dict):
            errors.append("Payload must be a JSON object")
            return False, errors
        
        # Check required fields
        missing_fields = [field for field in PayloadValidator.REQUIRED_FIELDS 
                         if field not in payload]
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Validate field types and lengths
        if not PayloadValidator._validate_field_types(payload, errors):
            return False, errors
        
        # Check for excessive nesting
        if PayloadValidator._get_nested_depth(payload) > PayloadValidator.MAX_NESTED_DEPTH:
            errors.append(f"Payload nested too deeply (max {PayloadValidator.MAX_NESTED_DEPTH} levels)")
        
        # Validate submission time format
        if '_submission_time' in payload:
            if not PayloadValidator._validate_datetime_format(payload['_submission_time']):
                errors.append("Invalid _submission_time format")
        
        # Log validation results
        if errors:
            logger.warning(f"Payload validation failed: {'; '.join(errors)}")
        else:
            logger.debug("Payload validation successful")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_field_types(payload: Dict[str, Any], errors: List[str], prefix: str = "") -> bool:
        """Recursively validate field types and lengths."""
        for key, value in payload.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, str) and len(value) > PayloadValidator.MAX_FIELD_LENGTH:
                errors.append(f"Field '{full_key}' exceeds maximum length ({PayloadValidator.MAX_FIELD_LENGTH})")
            
            elif isinstance(value, dict):
                PayloadValidator._validate_field_types(value, errors, full_key)
            
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        PayloadValidator._validate_field_types(item, errors, f"{full_key}[{i}]")
                    elif isinstance(item, str) and len(item) > PayloadValidator.MAX_FIELD_LENGTH:
                        errors.append(f"Field '{full_key}[{i}]' exceeds maximum length")
        
        return len(errors) == 0
    
    @staticmethod
    def _get_nested_depth(obj: Any, current_depth: int = 0) -> int:
        """Calculate the maximum nesting depth of a dictionary/list structure."""
        if current_depth > PayloadValidator.MAX_NESTED_DEPTH:
            return current_depth
        
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(PayloadValidator._get_nested_depth(v, current_depth + 1) for v in obj.values())
        
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(PayloadValidator._get_nested_depth(item, current_depth + 1) for item in obj)
        
        return current_depth
    
    @staticmethod
    def _validate_datetime_format(datetime_str: str) -> bool:
        """Validate datetime string format."""
        formats_to_try = [
            '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO format with microseconds
            '%Y-%m-%dT%H:%M:%SZ',     # ISO format without microseconds
            '%Y-%m-%d %H:%M:%S',      # Simple format
            '%Y-%m-%dT%H:%M:%S.%f%z', # With timezone
        ]
        
        for fmt in formats_to_try:
            try:
                datetime.strptime(datetime_str, fmt)
                return True
            except ValueError:
                continue
        
        return False
    
    @staticmethod
    def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize payload by removing potentially problematic content.
        
        Returns:
            Sanitized payload
        """
        sanitized = {}
        
        def sanitize_value(value: Any) -> Any:
            if isinstance(value, str):
                # Remove null bytes and excessive whitespace
                return value.replace('\x00', '').strip()
            elif isinstance(value, dict):
                return {k: sanitize_value(v) for k, v in value.items() 
                       if k and not k.startswith('__')}
            elif isinstance(value, list):
                return [sanitize_value(item) for item in value]
            else:
                return value
        
        for key, value in payload.items():
            # Skip private/system fields that might cause issues
            if key and not key.startswith('__'):
                sanitized[key] = sanitize_value(value)
        
        logger.debug(f"Sanitized payload: removed {len(payload) - len(sanitized)} fields")
        return sanitized
