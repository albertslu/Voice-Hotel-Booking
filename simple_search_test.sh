sh #!/bin/bash

# Simple Search Hotel Test Script
# This script tests the search_hotel webhook endpoint with detailed logging

set -e

# Configuration
BASE_URL="${BASE_URL:-https://many-birds-rest.loca.lt}"
WEBHOOK_ENDPOINT="/webhook/vapi"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_DIR="./search_test_results"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Test basic connectivity
test_connectivity() {
    log_info "Testing connectivity to $BASE_URL/webhook/test"
    
    local response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/webhook/test")
    local http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
    local body=$(echo "$response" | sed '/HTTP_CODE:/d')
    
    echo "HTTP Code: $http_code"
    echo "Response Body: $body"
    
    if [ "$http_code" = "200" ]; then
        log_success "Connectivity test passed"
        return 0
    else
        log_error "Connectivity test failed (HTTP $http_code)"
        return 1
    fi
}

# Test search hotel function
test_search_hotel() {
    log_info "Testing search_hotel function"
    
    local test_data='{
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "test_search_call",
                    "function": {
                        "name": "search_hotel",
                        "arguments": {
                            "check_in_date": "2025-10-15",
                            "check_out_date": "2025-10-18",
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
    
    log_info "Sending request to $BASE_URL$WEBHOOK_ENDPOINT"
    echo "Request data:"
    echo "$test_data" | jq . 2>/dev/null || echo "$test_data"
    
    local output_file="$OUTPUT_DIR/search_hotel_test_$TIMESTAMP.log"
    
    # Make the request and capture both response and HTTP code
    local response=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$test_data" \
        "$BASE_URL$WEBHOOK_ENDPOINT")
    
    # Save full response to file
    echo "=== SEARCH HOTEL TEST RESPONSE ===" > "$output_file"
    echo "Timestamp: $(date)" >> "$output_file"
    echo "URL: $BASE_URL$WEBHOOK_ENDPOINT" >> "$output_file"
    echo "Request Data:" >> "$output_file"
    echo "$test_data" >> "$output_file"
    echo "" >> "$output_file"
    echo "Response:" >> "$output_file"
    echo "$response" >> "$output_file"
    
    # Parse response
    local http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
    local body=$(echo "$response" | sed '/HTTP_CODE:/d')
    
    echo ""
    log_info "HTTP Response Code: $http_code"
    echo "Response Body:"
    echo "$body" | jq . 2>/dev/null || echo "$body"
    
    # Analyze response
    if [ "$http_code" = "200" ]; then
        log_success "Search hotel request successful (HTTP 200)"
        
        # Check if response is valid JSON
        if echo "$body" | jq . >/dev/null 2>&1; then
            log_success "Response is valid JSON"
            
            # Check for expected fields
            local has_results=$(echo "$body" | jq -r '.results // empty' 2>/dev/null)
            if [ -n "$has_results" ]; then
                log_success "Response contains 'results' field"
                
                # Extract key information
                local tool_call_id=$(echo "$body" | jq -r '.results[0].toolCallId // empty' 2>/dev/null)
                local result_message=$(echo "$body" | jq -r '.results[0].result // empty' 2>/dev/null)
                local session_id=$(echo "$body" | jq -r '.results[0].data.session_id // empty' 2>/dev/null)
                
                echo "Tool Call ID: $tool_call_id"
                echo "Session ID: $session_id"
                echo "Result Message: $result_message"
                
                # Check if we got a proper search result
                if [[ "$result_message" == *"found"* ]] || [[ "$result_message" == *"options"* ]]; then
                    log_success "Search appears to have returned hotel options"
                else
                    log_warning "Search response doesn't contain expected hotel options"
                fi
            else
                log_warning "Response missing 'results' field"
            fi
        else
            log_error "Response is not valid JSON"
        fi
    else
        log_error "Search hotel request failed (HTTP $http_code)"
    fi
    
    log_info "Full response saved to: $output_file"
    return 0
}


# Generate summary report
generate_summary() {
    local report_file="$OUTPUT_DIR/search_test_summary_$TIMESTAMP.txt"
    
    log_info "Generating summary report: $report_file"
    
    {
        echo "Search Hotel Function Test Summary"
        echo "=================================="
        echo "Timestamp: $(date)"
        echo "Base URL: $BASE_URL"
        echo "Webhook Endpoint: $WEBHOOK_ENDPOINT"
        echo ""
        echo "Test Results:"
        echo "============="
        echo "This test focused specifically on the search_hotel webhook endpoint."
        echo "Check the individual log files in this directory for detailed responses."
        echo ""
        echo "Files generated:"
        ls -la "$OUTPUT_DIR"/*_$TIMESTAMP.* 2>/dev/null || echo "No files found"
        
    } > "$report_file"
    
    log_success "Summary report generated: $report_file"
}

# Main execution
main() {
    log_info "Starting simple search hotel test"
    log_info "Base URL: $BASE_URL"
    log_info "Output Directory: $OUTPUT_DIR"
    echo ""
    
    # Test connectivity
    if ! test_connectivity; then
        log_error "Cannot connect to API. Exiting."
        exit 1
    fi
    
    echo ""
    
    # Test search hotel function
    test_search_hotel
    
    echo ""

    
    echo ""
    
    # Generate summary
    generate_summary
    
    log_success "Search hotel tests completed. Check $OUTPUT_DIR for detailed results."
}

# Run main function
main "$@"
