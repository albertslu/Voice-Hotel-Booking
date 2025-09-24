# VAPI Webhook Testing

This document describes how to use the `check_vapi_webhooks.sh` script to test and validate the VAPI webhook endpoints for the Voice Hotel Booking system.

## Overview

The `check_vapi_webhooks.sh` script provides comprehensive testing capabilities for the VAPI webhook endpoints, including:

- Basic connectivity testing
- Function call validation (search_hotel, book_hotel_1, book_hotel_2, start_over)
- Error handling and validation testing
- Load testing
- Response validation and JSON parsing
- Detailed logging and reporting

## Prerequisites

- `curl` - for making HTTP requests
- `jq` - for JSON validation and parsing (optional but recommended)
- Access to the running FastAPI server

## Usage

### Basic Usage

```bash
# Run all tests against localhost:8000
./check_vapi_webhooks.sh

# Run with verbose output
./check_vapi_webhooks.sh -v

# Test against a different URL
./check_vapi_webhooks.sh -u https://api.example.com
```

### Command Line Options

- `-u, --url URL` - Base URL for the API (default: http://localhost:8000)
- `-v, --verbose` - Enable verbose output
- `-h, --help` - Show help message
- `-o, --output DIR` - Output directory for test results (default: ./webhook_test_results)

### Test Types

- `all` - Run all tests (default)
- `connectivity` - Test basic connectivity only
- `search` - Test search_hotel webhook only
- `booking` - Test booking webhooks only
- `validation` - Test validation and error handling only
- `load` - Run load test only

### Examples

```bash
# Test only connectivity
./check_vapi_webhooks.sh connectivity

# Test search functionality with verbose output
./check_vapi_webhooks.sh -v search

# Test against production API
./check_vapi_webhooks.sh -u https://api.guestara.ai

# Run load test only
./check_vapi_webhooks.sh load

# Custom output directory
./check_vapi_webhooks.sh --output /tmp/webhook_tests all
```

## Test Coverage

### 1. Connectivity Test
- Tests the `/webhook/test` endpoint
- Verifies basic server connectivity
- Validates response format

### 2. Search Hotel Test
- Tests the `search_hotel` function call
- Validates required parameters (check_in_date, check_out_date, adults)
- Checks response structure and JSON validity
- Tests with sample data for SF Proper Hotel

### 3. Booking Tests
- **book_hotel_1**: Tests room selection functionality
- **book_hotel_2**: Tests complete booking with guest and payment info
- Validates session management
- Tests parameter validation

### 4. Start Over Test
- Tests the `start_over` function
- Validates session clearing functionality

### 5. Validation Tests
- **Invalid Function**: Tests unknown function handling
- **Malformed JSON**: Tests JSON parsing error handling
- **Non-tool-calls**: Tests non-function-call message handling

### 6. Load Test
- Runs 10 concurrent requests
- Tests server stability under load
- Measures success rate

## Output

### Console Output
The script provides colored console output:
- 🔵 **Blue**: Info messages
- 🟢 **Green**: Success messages
- 🟡 **Yellow**: Warning messages
- 🔴 **Red**: Error messages

### Test Results
All test results are saved to JSON files in the output directory:
- `search_hotel_test_TIMESTAMP.json`
- `book_hotel_1_test_TIMESTAMP.json`
- `book_hotel_2_test_TIMESTAMP.json`
- `start_over_test_TIMESTAMP.json`
- `invalid_function_test_TIMESTAMP.json`
- `malformed_json_test_TIMESTAMP.json`
- `non_tool_calls_test_TIMESTAMP.json`

### Test Report
A comprehensive test report is generated:
- `webhook_test_report_TIMESTAMP.txt`
- Includes all test results, configuration, and timestamps

## Environment Variables

You can set these environment variables instead of using command line options:

```bash
export BASE_URL="https://api.example.com"
export VERBOSE="true"
./check_vapi_webhooks.sh
```

## Expected Responses

### Successful search_hotel Response
```json
{
  "results": [
    {
      "toolCallId": "test_call_1",
      "result": "Perfect! I found the ideal options for your stay...",
      "data": {
        "session_id": "booking_1234567890",
        "room_options": [...],
        "search_completed": true
      }
    }
  ]
}
```

### Successful booking Response
```json
{
  "result": "Perfect! I've selected the Proper King Room...",
  "success": true,
  "step": 1,
  "session_id": "booking_1234567890",
  "selected_room": {...},
  "next_step": "collect_guest_and_payment_info"
}
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure the FastAPI server is running
   - Check the BASE_URL is correct
   - Verify the port is accessible

2. **JSON Parse Errors**
   - Check if `jq` is installed for JSON validation
   - Review server logs for malformed responses

3. **Test Failures**
   - Check server logs for detailed error information
   - Verify all required environment variables are set
   - Ensure Redis is running for session management

### Debug Mode

Use verbose mode for detailed debugging:
```bash
./check_vapi_webhooks.sh -v all
```

This will show:
- Request details
- Response codes and bodies
- JSON validation results
- Detailed error messages

## Integration with CI/CD

The script can be integrated into CI/CD pipelines:

```bash
# Exit with error code if any test fails
./check_vapi_webhooks.sh all
if [ $? -ne 0 ]; then
    echo "Webhook tests failed"
    exit 1
fi
```

## Security Notes

- The script uses test data with fake credit card numbers
- No real payment processing occurs during testing
- Session IDs are generated for testing purposes only
- All test data is logged for debugging purposes
