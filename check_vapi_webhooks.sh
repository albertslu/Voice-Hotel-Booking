#!/bin/bash

# VAPI Webhook Testing Script
# This script tests the VAPI webhook endpoints for the Voice Hotel Booking system

set -e  # Exit on any error

# Configuration
# BASE_URL="${BASE_URL:-http://localhost:8000}"
# BASE_URL="${BASE_URL:-https://api.guestara.ai}"
BASE_URL="${BASE_URL:-https://blue-times-glow.loca.lt}"
WEBHOOK_ENDPOINT="/webhook/vapi"
TEST_ENDPOINT="/webhook/test"
VERBOSE="${VERBOSE:-false}"
OUTPUT_DIR="./webhook_test_results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_verbose() {
    if [ "$VERBOSE" = "true" ]; then
        echo -e "${BLUE}[VERBOSE]${NC} $1"
    fi
}

# Function to make HTTP requests
make_request() {
    local method="$1"
    local url="$2"
    local data="$3"
    local headers="$4"
    local output_file="$5"
    
    log_verbose "Making $method request to $url"
    if [ -n "$data" ]; then
        log_verbose "Request data: $data"
    fi
    
    local curl_cmd="curl -s -w '\n%{http_code}' -X $method"
    
    if [ -n "$headers" ]; then
        curl_cmd="$curl_cmd $headers"
    fi
    
    if [ -n "$data" ]; then
        curl_cmd="$curl_cmd -d '$data'"
    fi
    
    curl_cmd="$curl_cmd '$url'"
    
    if [ -n "$output_file" ]; then
        eval "$curl_cmd" > "$output_file" 2>&1
        local response_code=$(tail -n1 "$output_file")
        local response_body=$(sed '$d' "$output_file")
    else
        local response=$(eval "$curl_cmd")
        local response_code=$(echo "$response" | tail -n1)
        local response_body=$(echo "$response" | sed '$d')
    fi
    
    echo "$response_code|$response_body"
}

# Function to validate JSON response
validate_json() {
    local json_string="$1"
    if echo "$json_string" | jq . >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to test basic connectivity
test_connectivity() {
    log_info "Testing basic connectivity to $BASE_URL"
    
    local result=$(make_request "GET" "$BASE_URL$TEST_ENDPOINT" "" "" "")
    local response_code=$(echo "$result" | cut -d'|' -f1)
    local response_body=$(echo "$result" | cut -d'|' -f2-)
    
    if [ "$response_code" = "200" ]; then
        log_success "Basic connectivity test passed"
        log_verbose "Response: $response_body"
        return 0
    else
        log_error "Basic connectivity test failed (HTTP $response_code)"
        log_verbose "Response: $response_body"
        return 1
    fi
}

# Function to test search_hotel webhook
test_search_hotel() {
    log_info "Testing search_hotel webhook"
    
    local test_data='{
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "test_call_1",
                    "function": {
                        "name": "search_hotel",
                        "arguments": {
                            "check_in_date": "2025-02-15",
                            "check_out_date": "2025-02-17",
                            "adults": 2,
                            "occasion": "business"
                        }
                    }
                }
            ]
        },
        "call": {
            "id": "test_call_123"
        }
    }'
    
    local output_file="$OUTPUT_DIR/search_hotel_test_$TIMESTAMP.json"
    local result=$(make_request "POST" "$BASE_URL$WEBHOOK_ENDPOINT" "$test_data" "-H 'Content-Type: application/json'" "$output_file")
    local response_code=$(echo "$result" | cut -d'|' -f1)
    local response_body=$(echo "$result" | cut -d'|' -f2-)
    
    if [ "$response_code" = "200" ]; then
        if validate_json "$response_body"; then
            log_success "search_hotel webhook test passed"
            log_verbose "Response saved to: $output_file"
            
            # Check for expected fields in response
            local has_results=$(echo "$response_body" | jq -r '.results // empty')
            if [ -n "$has_results" ]; then
                log_success "Response contains expected 'results' field"
            else
                log_warning "Response missing 'results' field"
            fi
        else
            log_error "search_hotel webhook returned invalid JSON"
        fi
    else
        log_error "search_hotel webhook test failed (HTTP $response_code)"
        log_verbose "Response: $response_body"
    fi
}

# Function to test book_hotel_1 webhook
test_book_hotel_1() {
    log_info "Testing book_hotel_1 webhook"
    
    local test_data='{
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "test_call_2",
                    "function": {
                        "name": "book_hotel_1",
                        "arguments": {
                            "session_id": "test_session_123",
                            "room_choice": 1
                        }
                    }
                }
            ]
        },
        "call": {
            "id": "test_call_456"
        }
    }'
    
    local output_file="$OUTPUT_DIR/book_hotel_1_test_$TIMESTAMP.json"
    local result=$(make_request "POST" "$BASE_URL$WEBHOOK_ENDPOINT" "$test_data" "-H 'Content-Type: application/json'" "$output_file")
    local response_code=$(echo "$result" | cut -d'|' -f1)
    local response_body=$(echo "$result" | cut -d'|' -f2-)
    
    if [ "$response_code" = "200" ]; then
        if validate_json "$response_body"; then
            log_success "book_hotel_1 webhook test passed"
            log_verbose "Response saved to: $output_file"
        else
            log_error "book_hotel_1 webhook returned invalid JSON"
        fi
    else
        log_warning "book_hotel_1 webhook test returned HTTP $response_code (expected for invalid session)"
        log_verbose "Response: $response_body"
    fi
}

# Function to test book_hotel_2 webhook
test_book_hotel_2() {
    log_info "Testing book_hotel_2 webhook"
    
    local test_data='{
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "test_call_3",
                    "function": {
                        "name": "book_hotel_2",
                        "arguments": {
                            "session_id": "test_session_123",
                            "first_name": "John",
                            "last_name": "Doe",
                            "email": "john.doe@example.com",
                            "phone": "555-123-4567",
                            "address": "123 Main St",
                            "zip_code": "94102",
                            "city": "San Francisco",
                            "state": "CA",
                            "country": "USA",
                            "card_number": "4111111111111111",
                            "expiry_month": "12",
                            "expiry_year": "2025",
                            "cvv": "123",
                            "cardholder_name": "John Doe"
                        }
                    }
                }
            ]
        },
        "call": {
            "id": "test_call_789"
        }
    }'
    
    local output_file="$OUTPUT_DIR/book_hotel_2_test_$TIMESTAMP.json"
    local result=$(make_request "POST" "$BASE_URL$WEBHOOK_ENDPOINT" "$test_data" "-H 'Content-Type: application/json'" "$output_file")
    local response_code=$(echo "$result" | cut -d'|' -f1)
    local response_body=$(echo "$result" | cut -d'|' -f2-)
    
    if [ "$response_code" = "200" ]; then
        if validate_json "$response_body"; then
            log_success "book_hotel_2 webhook test passed"
            log_verbose "Response saved to: $output_file"
        else
            log_error "book_hotel_2 webhook returned invalid JSON"
        fi
    else
        log_warning "book_hotel_2 webhook test returned HTTP $response_code (expected for invalid session)"
        log_verbose "Response: $response_body"
    fi
}

# Function to test start_over webhook
test_start_over() {
    log_info "Testing start_over webhook"
    
    local test_data='{
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "test_call_4",
                    "function": {
                        "name": "start_over",
                        "arguments": {
                            "session_id": "test_session_123"
                        }
                    }
                }
            ]
        },
        "call": {
            "id": "test_call_101"
        }
    }'
    
    local output_file="$OUTPUT_DIR/start_over_test_$TIMESTAMP.json"
    local result=$(make_request "POST" "$BASE_URL$WEBHOOK_ENDPOINT" "$test_data" "-H 'Content-Type: application/json'" "$output_file")
    local response_code=$(echo "$result" | cut -d'|' -f1)
    local response_body=$(echo "$result" | cut -d'|' -f2-)
    
    if [ "$response_code" = "200" ]; then
        if validate_json "$response_body"; then
            log_success "start_over webhook test passed"
            log_verbose "Response saved to: $output_file"
        else
            log_error "start_over webhook returned invalid JSON"
        fi
    else
        log_error "start_over webhook test failed (HTTP $response_code)"
        log_verbose "Response: $response_body"
    fi
}

# Function to test invalid function call
test_invalid_function() {
    log_info "Testing invalid function call"
    
    local test_data='{
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "test_call_5",
                    "function": {
                        "name": "invalid_function",
                        "arguments": {}
                    }
                }
            ]
        },
        "call": {
            "id": "test_call_999"
        }
    }'
    
    local output_file="$OUTPUT_DIR/invalid_function_test_$TIMESTAMP.json"
    local result=$(make_request "POST" "$BASE_URL$WEBHOOK_ENDPOINT" "$test_data" "-H 'Content-Type: application/json'" "$output_file")
    local response_code=$(echo "$result" | cut -d'|' -f1)
    local response_body=$(echo "$result" | cut -d'|' -f2-)
    
    if [ "$response_code" = "400" ]; then
        log_success "Invalid function call correctly rejected (HTTP 400)"
        log_verbose "Response: $response_body"
    else
        log_warning "Invalid function call returned HTTP $response_code (expected 400)"
        log_verbose "Response: $response_body"
    fi
}

# Function to test malformed JSON
test_malformed_json() {
    log_info "Testing malformed JSON"
    
    local test_data='{"message": {"type": "tool-calls", "toolCalls": [{"id": "test", "function": {"name": "search_hotel"'
    
    local output_file="$OUTPUT_DIR/malformed_json_test_$TIMESTAMP.json"
    local result=$(make_request "POST" "$BASE_URL$WEBHOOK_ENDPOINT" "$test_data" "-H 'Content-Type: application/json'" "$output_file")
    local response_code=$(echo "$result" | cut -d'|' -f1)
    local response_body=$(echo "$result" | cut -d'|' -f2-)
    
    if [ "$response_code" = "422" ] || [ "$response_code" = "400" ]; then
        log_success "Malformed JSON correctly rejected (HTTP $response_code)"
        log_verbose "Response: $response_body"
    else
        log_warning "Malformed JSON returned HTTP $response_code (expected 400 or 422)"
        log_verbose "Response: $response_body"
    fi
}

# Function to test non-tool-calls message
test_non_tool_calls() {
    log_info "Testing non-tool-calls message"
    
    local test_data='{
        "message": {
            "type": "user-message",
            "content": "Hello, I want to book a hotel"
        },
        "call": {
            "id": "test_call_888"
        }
    }'
    
    local output_file="$OUTPUT_DIR/non_tool_calls_test_$TIMESTAMP.json"
    local result=$(make_request "POST" "$BASE_URL$WEBHOOK_ENDPOINT" "$test_data" "-H 'Content-Type: application/json'" "$output_file")
    local response_code=$(echo "$result" | cut -d'|' -f1)
    local response_body=$(echo "$result" | cut -d'|' -f2-)
    
    if [ "$response_code" = "200" ]; then
        if validate_json "$response_body"; then
            log_success "Non-tool-calls message handled correctly"
            log_verbose "Response: $response_body"
        else
            log_error "Non-tool-calls message returned invalid JSON"
        fi
    else
        log_warning "Non-tool-calls message returned HTTP $response_code"
        log_verbose "Response: $response_body"
    fi
}

# Function to run load test
run_load_test() {
    log_info "Running load test (10 concurrent requests)"
    
    local test_data='{
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "load_test_call",
                    "function": {
                        "name": "search_hotel",
                        "arguments": {
                            "check_in_date": "2025-02-15",
                            "check_out_date": "2025-02-17",
                            "adults": 2
                        }
                    }
                }
            ]
        },
        "call": {
            "id": "load_test_call"
        }
    }'
    
    local success_count=0
    local total_requests=10
    
    for i in $(seq 1 $total_requests); do
        local result=$(make_request "POST" "$BASE_URL$WEBHOOK_ENDPOINT" "$test_data" "-H 'Content-Type: application/json'" "")
        local response_code=$(echo "$result" | cut -d'|' -f1)
        
        if [ "$response_code" = "200" ]; then
            ((success_count++))
        fi
        
        log_verbose "Request $i/$total_requests: HTTP $response_code"
    done
    
    log_info "Load test completed: $success_count/$total_requests requests successful"
    
    if [ $success_count -eq $total_requests ]; then
        log_success "All load test requests passed"
    elif [ $success_count -gt $((total_requests / 2)) ]; then
        log_warning "Most load test requests passed ($success_count/$total_requests)"
    else
        log_error "Load test failed ($success_count/$total_requests requests successful)"
    fi
}

# Function to generate test report
generate_report() {
    local report_file="$OUTPUT_DIR/webhook_test_report_$TIMESTAMP.txt"
    
    log_info "Generating test report: $report_file"
    
    {
        echo "VAPI Webhook Test Report"
        echo "========================"
        echo "Timestamp: $(date)"
        echo "Base URL: $BASE_URL"
        echo "Webhook Endpoint: $WEBHOOK_ENDPOINT"
        echo ""
        echo "Test Results:"
        echo "============="
        
        # List all test result files
        for file in "$OUTPUT_DIR"/*_test_$TIMESTAMP.json; do
            if [ -f "$file" ]; then
                echo "Test: $(basename "$file")"
                echo "Content:"
                cat "$file" | jq . 2>/dev/null || cat "$file"
                echo ""
                echo "---"
                echo ""
            fi
        done
        
        echo "Configuration:"
        echo "=============="
        echo "Base URL: $BASE_URL"
        echo "Verbose Mode: $VERBOSE"
        echo "Output Directory: $OUTPUT_DIR"
        
    } > "$report_file"
    
    log_success "Test report generated: $report_file"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [TEST_TYPES]"
    echo ""
    echo "Options:"
    # echo "  -u, --url URL          Base URL for the API (default: http://localhost:8000)"
    echo "  -u, --url URL          Base URL for the API (default: http://localhost:8000)"
    echo "  -v, --verbose          Enable verbose output"
    echo "  -h, --help             Show this help message"
    echo "  -o, --output DIR       Output directory for test results (default: ./webhook_test_results)"
    echo ""
    echo "Test Types:"
    echo "  all                    Run all tests (default)"
    echo "  connectivity          Test basic connectivity only"
    echo "  search                Test search_hotel webhook only"
    echo "  booking               Test booking webhooks only"
    echo "  validation            Test validation and error handling only"
    echo "  load                  Run load test only"
    echo ""
    echo "Environment Variables:"
    echo "  BASE_URL              Base URL for the API"
    echo "  VERBOSE               Enable verbose output (true/false)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests"
    echo "  $0 -u https://api.example.com        # Test against production API"
    echo "  $0 -v search                         # Verbose search test only"
    echo "  $0 --output /tmp/results all         # Custom output directory"
}

# Main function
main() {
    local test_types="all"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -u|--url)
                BASE_URL="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE="true"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            -o|--output)
                OUTPUT_DIR="$2"
                mkdir -p "$OUTPUT_DIR"
                shift 2
                ;;
            all|connectivity|search|booking|validation|load)
                test_types="$1"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    log_info "Starting VAPI webhook tests"
    log_info "Base URL: $BASE_URL"
    log_info "Output Directory: $OUTPUT_DIR"
    log_info "Verbose Mode: $VERBOSE"
    echo ""
    
    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        log_warning "jq is not installed. JSON validation will be limited."
    fi
    
    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
    
    # Run tests based on type
    case $test_types in
        all)
            test_connectivity || exit 1
            test_search_hotel
            test_book_hotel_1
            test_book_hotel_2
            test_start_over
            test_invalid_function
            test_malformed_json
            test_non_tool_calls
            run_load_test
            ;;
        connectivity)
            test_connectivity
            ;;
        search)
            test_connectivity || exit 1
            test_search_hotel
            ;;
        booking)
            test_connectivity || exit 1
            test_book_hotel_1
            test_book_hotel_2
            test_start_over
            ;;
        validation)
            test_connectivity || exit 1
            test_invalid_function
            test_malformed_json
            test_non_tool_calls
            ;;
        load)
            test_connectivity || exit 1
            run_load_test
            ;;
    esac
    
    # Generate report
    generate_report
    
    log_success "All tests completed. Check $OUTPUT_DIR for detailed results."
}

# Run main function with all arguments
main "$@"
