import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first to get the standard error response.
    response = exception_handler(exc, context)

    if response is not None:
        message = "An error occurred with your request."
        errors = {}

        if isinstance(response.data, dict):
            if 'detail' in response.data:
                message = str(response.data['detail'])
                errors = response.data
            else:
                message = "Validation error. Please verify the submitted information."
                errors = response.data
        elif isinstance(response.data, list):
            message = "; ".join(str(item) for item in response.data)
            errors = {'non_field_errors': response.data}
        else:
            message = str(response.data)

        code = None
        if isinstance(errors, dict) and 'code' in errors:
            code_val = errors['code']
            if isinstance(code_val, list) and len(code_val) > 0:
                code = str(code_val[0])
            else:
                code = str(code_val)
        elif hasattr(exc, 'get_codes'):
            try:
                code_val = exc.get_codes()
                if isinstance(code_val, str):
                    code = code_val
                elif isinstance(code_val, dict) and 'code' in code_val:
                    c = code_val['code']
                    code = str(c[0]) if isinstance(c, list) and c else str(c)
            except Exception:
                pass

        custom_data = {
            'success': False,
            'message': message,
            'errors': errors,
            'status_code': response.status_code
        }
        if code:
            custom_data['code'] = code
        response.data = custom_data
        return response

    # Handle unhandled server exceptions (500)
    view_name = context.get('view', None)
    logger.exception(f"Unhandled server error in {view_name}: {exc}")

    return Response({
        'success': False,
        'message': 'A server error occurred. Our team has been notified. Please try again shortly.',
        'errors': {'server': ['Internal server error']},
        'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
