"""Tests for request canonicalization engine."""

import base64
import pytest
from localzure.gateway.canonicalizer import (
    RequestCanonicalizer,
    CanonicalVersion,
    ServiceType,
    parse_authorization_header,
)


class TestCanonicalizedHeaders:
    """Test AC2: Canonicalized headers are sorted and formatted per Azure spec."""

    def test_basic_headers(self):
        """Test basic x-ms-* header canonicalization."""
        canonicalizer = RequestCanonicalizer()
        headers = {
            "x-ms-version": "2021-08-06",
            "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT"
        }
        
        canonical_headers = canonicalizer._build_canonical_headers(headers)
        
        # Headers should be sorted alphabetically
        expected = "x-ms-date:Tue, 04 Dec 2025 10:30:00 GMT\nx-ms-version:2021-08-06"
        assert canonical_headers == expected

    def test_headers_sorted_alphabetically(self):
        """Test that headers are sorted lexicographically."""
        canonicalizer = RequestCanonicalizer()
        headers = {
            "x-ms-version": "2021-08-06",
            "x-ms-blob-type": "BlockBlob",
            "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT",
            "x-ms-client-request-id": "123-456"
        }
        
        canonical_headers = canonicalizer._build_canonical_headers(headers)
        
        lines = canonical_headers.split("\n")
        assert lines[0].startswith("x-ms-blob-type:")
        assert lines[1].startswith("x-ms-client-request-id:")
        assert lines[2].startswith("x-ms-date:")
        assert lines[3].startswith("x-ms-version:")

    def test_case_insensitive_header_names(self):
        """Test that header names are converted to lowercase."""
        canonicalizer = RequestCanonicalizer()
        headers = {
            "X-MS-Version": "2021-08-06",
            "x-ms-DATE": "Tue, 04 Dec 2025 10:30:00 GMT",
            "X-Ms-Blob-Type": "BlockBlob"
        }
        
        canonical_headers = canonicalizer._build_canonical_headers(headers)
        
        # All header names should be lowercase
        for line in canonical_headers.split("\n"):
            header_name = line.split(":")[0]
            assert header_name == header_name.lower()

    def test_non_ms_headers_excluded(self):
        """Test that non x-ms-* headers are excluded."""
        canonicalizer = RequestCanonicalizer()
        headers = {
            "Content-Type": "application/json",
            "Authorization": "SharedKey account:signature",
            "x-ms-version": "2021-08-06",
            "Host": "myaccount.blob.core.windows.net"
        }
        
        canonical_headers = canonicalizer._build_canonical_headers(headers)
        
        assert "x-ms-version:2021-08-06" in canonical_headers
        assert "Content-Type" not in canonical_headers
        assert "Authorization" not in canonical_headers
        assert "Host" not in canonical_headers

    def test_whitespace_normalization(self):
        """Test that values with extra whitespace are normalized."""
        canonicalizer = RequestCanonicalizer()
        headers = {
            "x-ms-version": "  2021-08-06  ",  # Leading/trailing spaces
            "x-ms-meta-key": "value   with   spaces"  # Multiple spaces
        }
        
        canonical_headers = canonicalizer._build_canonical_headers(headers)
        
        assert "x-ms-meta-key:value with spaces" in canonical_headers
        assert "x-ms-version:2021-08-06" in canonical_headers

    def test_empty_headers(self):
        """Test AC6: Handle empty headers correctly."""
        canonicalizer = RequestCanonicalizer()
        headers = {}
        
        canonical_headers = canonicalizer._build_canonical_headers(headers)
        
        assert canonical_headers == ""


class TestCanonicalizedResource:
    """Test AC3: Canonicalized resource includes account name and path."""

    def test_basic_blob_resource(self):
        """Test basic blob resource canonicalization."""
        canonicalizer = RequestCanonicalizer()
        url = "https://myaccount.blob.core.windows.net/container/blob"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        assert canonical_resource == "/myaccount/container/blob"

    def test_account_name_included(self):
        """Test that account name is always included in resource."""
        canonicalizer = RequestCanonicalizer()
        url = "https://storage123.blob.core.windows.net/mycontainer"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "storage123", ServiceType.BLOB
        )
        
        assert canonical_resource.startswith("/storage123/")

    def test_nested_path(self):
        """Test nested path in canonical resource."""
        canonicalizer = RequestCanonicalizer()
        url = "https://myaccount.blob.core.windows.net/container/folder1/folder2/file.txt"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        assert canonical_resource == "/myaccount/container/folder1/folder2/file.txt"

    def test_root_path(self):
        """Test canonical resource with root path."""
        canonicalizer = RequestCanonicalizer()
        url = "https://myaccount.blob.core.windows.net/"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        assert canonical_resource == "/myaccount/"


class TestQueryParametersInCanonicalResource:
    """Test AC4: Query parameters are included in canonical form when required."""

    def test_query_params_included_2019(self):
        """Test query parameters included in 2019-02-02 version."""
        canonicalizer = RequestCanonicalizer(version=CanonicalVersion.VERSION_2019_02_02)
        url = "https://myaccount.blob.core.windows.net/container/blob?comp=metadata&timeout=30"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        assert "/myaccount/container/blob" in canonical_resource
        assert "comp:metadata" in canonical_resource
        assert "timeout:30" in canonical_resource

    def test_query_params_sorted(self):
        """Test query parameters are sorted alphabetically."""
        canonicalizer = RequestCanonicalizer(version=CanonicalVersion.VERSION_2019_02_02)
        url = "https://myaccount.blob.core.windows.net/container?timeout=30&comp=metadata&sv=2021-08-06"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        lines = canonical_resource.split("\n")
        assert lines[0] == "/myaccount/container"
        assert lines[1] == "comp:metadata"
        assert lines[2] == "sv:2021-08-06"
        assert lines[3] == "timeout:30"

    def test_query_params_lowercase_names(self):
        """Test query parameter names are converted to lowercase."""
        canonicalizer = RequestCanonicalizer(version=CanonicalVersion.VERSION_2019_02_02)
        url = "https://myaccount.blob.core.windows.net/container?COMP=metadata&Timeout=30"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        assert "comp:metadata" in canonical_resource
        assert "timeout:30" in canonical_resource
        assert "COMP" not in canonical_resource
        assert "Timeout" not in canonical_resource

    def test_multiple_param_values(self):
        """Test multiple values for same parameter."""
        canonicalizer = RequestCanonicalizer(version=CanonicalVersion.VERSION_2019_02_02)
        url = "https://myaccount.blob.core.windows.net/container?tag=value1&tag=value2"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        assert "tag:value1,value2" in canonical_resource

    def test_no_query_params(self):
        """Test resource without query parameters."""
        canonicalizer = RequestCanonicalizer(version=CanonicalVersion.VERSION_2019_02_02)
        url = "https://myaccount.blob.core.windows.net/container/blob"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        assert canonical_resource == "/myaccount/container/blob"
        assert "\n" not in canonical_resource


class TestCanonicalVersionSupport:
    """Test AC5: Different canonicalization versions are supported."""

    def test_version_2009_09_19(self):
        """Test 2009-09-19 version (no query params in resource)."""
        canonicalizer = RequestCanonicalizer(version=CanonicalVersion.VERSION_2009_09_19)
        url = "https://myaccount.blob.core.windows.net/container?comp=metadata"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        # Query params should NOT be included in 2009 version
        assert canonical_resource == "/myaccount/container"
        assert "comp" not in canonical_resource

    def test_version_2015_04_05(self):
        """Test 2015-04-05 version (includes query params)."""
        canonicalizer = RequestCanonicalizer(version=CanonicalVersion.VERSION_2015_04_05)
        url = "https://myaccount.blob.core.windows.net/container?comp=metadata"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        # Query params should be included in 2015+ versions
        assert "/myaccount/container" in canonical_resource
        assert "comp:metadata" in canonical_resource

    def test_version_2019_02_02(self):
        """Test 2019-02-02 version (latest, includes query params)."""
        canonicalizer = RequestCanonicalizer(version=CanonicalVersion.VERSION_2019_02_02)
        url = "https://myaccount.blob.core.windows.net/container?sv=2021-08-06"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        assert "/myaccount/container" in canonical_resource
        assert "sv:2021-08-06" in canonical_resource


class TestFullCanonicalization:
    """Test AC1: Gateway builds canonicalized strings for Blob/Queue/Table."""

    def test_blob_get_request(self):
        """Test full canonicalization for Blob GET request."""
        canonicalizer = RequestCanonicalizer()
        result = canonicalizer.canonicalize(
            method="GET",
            url="https://myaccount.blob.core.windows.net/container/blob",
            headers={
                "x-ms-version": "2021-08-06",
                "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT"
            },
            account_name="myaccount",
            service_type=ServiceType.BLOB
        )
        
        assert result.string_to_sign.startswith("GET\n")
        assert "x-ms-date:Tue, 04 Dec 2025 10:30:00 GMT" in result.string_to_sign
        assert "x-ms-version:2021-08-06" in result.string_to_sign
        assert "/myaccount/container/blob" in result.string_to_sign

    def test_blob_put_with_content(self):
        """Test canonicalization for Blob PUT with content headers."""
        canonicalizer = RequestCanonicalizer()
        result = canonicalizer.canonicalize(
            method="PUT",
            url="https://myaccount.blob.core.windows.net/container/blob",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": "1024",
                "x-ms-version": "2021-08-06",
                "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT",
                "x-ms-blob-type": "BlockBlob"
            },
            account_name="myaccount",
            service_type=ServiceType.BLOB
        )
        
        lines = result.string_to_sign.split("\n")
        assert lines[0] == "PUT"
        assert "1024" in result.string_to_sign  # Content-Length
        assert "application/octet-stream" in result.string_to_sign  # Content-Type

    def test_queue_message_operation(self):
        """Test canonicalization for Queue service."""
        canonicalizer = RequestCanonicalizer()
        result = canonicalizer.canonicalize(
            method="POST",
            url="https://myaccount.queue.core.windows.net/myqueue/messages",
            headers={
                "x-ms-version": "2021-08-06",
                "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT"
            },
            account_name="myaccount",
            service_type=ServiceType.QUEUE
        )
        
        assert "POST" in result.string_to_sign
        assert "/myaccount/myqueue/messages" in result.string_to_sign

    def test_table_query_operation(self):
        """Test canonicalization for Table service."""
        canonicalizer = RequestCanonicalizer()
        result = canonicalizer.canonicalize(
            method="GET",
            url="https://myaccount.table.core.windows.net/Customers()",
            headers={
                "x-ms-version": "2021-08-06",
                "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT"
            },
            account_name="myaccount",
            service_type=ServiceType.TABLE
        )
        
        # Table uses simpler format
        assert "GET" in result.string_to_sign
        assert "/myaccount/Customers()" in result.string_to_sign


class TestSignatureComputation:
    """Test AC7: HMAC-SHA256 signature validation works against test vectors."""

    def test_compute_signature_basic(self):
        """Test basic signature computation."""
        canonicalizer = RequestCanonicalizer()
        
        # Simple test with known values
        string_to_sign = "GET\n\n\n\n\n\n\n\n\n\n\n\nx-ms-date:Tue, 04 Dec 2025 10:30:00 GMT\nx-ms-version:2021-08-06\n/myaccount/container"
        
        # Base64-encoded key (for testing)
        account_key = base64.b64encode(b"secret_key_12345").decode('utf-8')
        
        signature = canonicalizer.compute_signature(string_to_sign, account_key)
        
        # Signature should be non-empty base64 string
        assert signature
        assert len(signature) > 0
        # Base64 should only contain valid characters
        base64.b64decode(signature)  # Should not raise

    def test_signature_deterministic(self):
        """Test that signature is deterministic."""
        canonicalizer = RequestCanonicalizer()
        
        string_to_sign = "GET\n\n\n\n\n\n\n\n\n\n\n\nx-ms-version:2021-08-06\n/myaccount/container"
        account_key = base64.b64encode(b"test_key").decode('utf-8')
        
        sig1 = canonicalizer.compute_signature(string_to_sign, account_key)
        sig2 = canonicalizer.compute_signature(string_to_sign, account_key)
        
        assert sig1 == sig2

    def test_different_keys_different_signatures(self):
        """Test that different keys produce different signatures."""
        canonicalizer = RequestCanonicalizer()
        
        string_to_sign = "GET\n\n\n\n\n\n\n\n\n\n\n\nx-ms-version:2021-08-06\n/myaccount/container"
        
        key1 = base64.b64encode(b"key1").decode('utf-8')
        key2 = base64.b64encode(b"key2").decode('utf-8')
        
        sig1 = canonicalizer.compute_signature(string_to_sign, key1)
        sig2 = canonicalizer.compute_signature(string_to_sign, key2)
        
        assert sig1 != sig2

    def test_validate_signature_success(self):
        """Test successful signature validation."""
        canonicalizer = RequestCanonicalizer()
        
        method = "GET"
        url = "https://myaccount.blob.core.windows.net/container/blob"
        headers = {
            "x-ms-version": "2021-08-06",
            "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT"
        }
        account_name = "myaccount"
        account_key = base64.b64encode(b"test_key_12345").decode('utf-8')
        
        # First, compute the expected signature
        result = canonicalizer.canonicalize(
            method=method,
            url=url,
            headers=headers,
            account_name=account_name
        )
        expected_sig = canonicalizer.compute_signature(result.string_to_sign, account_key)
        
        # Now validate
        valid = canonicalizer.validate_signature(
            method=method,
            url=url,
            headers=headers,
            account_name=account_name,
            account_key=account_key,
            provided_signature=expected_sig
        )
        
        assert valid is True

    def test_validate_signature_failure(self):
        """Test signature validation fails with wrong signature."""
        canonicalizer = RequestCanonicalizer()
        
        valid = canonicalizer.validate_signature(
            method="GET",
            url="https://myaccount.blob.core.windows.net/container",
            headers={"x-ms-version": "2021-08-06"},
            account_name="myaccount",
            account_key=base64.b64encode(b"correct_key").decode('utf-8'),
            provided_signature="wrong_signature_xyz=="
        )
        
        assert valid is False


class TestEmptyAndMissingValues:
    """Test AC6: Canonicalization handles empty headers and missing values correctly."""

    def test_missing_content_headers(self):
        """Test canonicalization without content headers."""
        canonicalizer = RequestCanonicalizer()
        result = canonicalizer.canonicalize(
            method="GET",
            url="https://myaccount.blob.core.windows.net/container",
            headers={
                "x-ms-version": "2021-08-06",
                "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT"
            },
            account_name="myaccount"
        )
        
        # String should have empty lines for missing headers
        lines = result.string_to_sign.split("\n")
        assert lines[0] == "GET"
        # Next several lines should be empty (no content headers)
        assert lines[1] == ""  # Content-Encoding
        assert lines[2] == ""  # Content-Language
        assert lines[3] == ""  # Content-Length

    def test_empty_header_values(self):
        """Test headers with empty values."""
        canonicalizer = RequestCanonicalizer()
        headers = {
            "x-ms-version": "",
            "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT"
        }
        
        canonical_headers = canonicalizer._build_canonical_headers(headers)
        
        # Empty values should still be included
        assert "x-ms-version:" in canonical_headers

    def test_missing_date_header(self):
        """Test canonicalization without Date header."""
        canonicalizer = RequestCanonicalizer()
        result = canonicalizer.canonicalize(
            method="GET",
            url="https://myaccount.blob.core.windows.net/container",
            headers={
                "x-ms-version": "2021-08-06",
                "x-ms-date": "Tue, 04 Dec 2025 10:30:00 GMT"
            },
            account_name="myaccount"
        )
        
        # Should have empty Date line in string-to-sign
        assert "\n\n" in result.string_to_sign


class TestAuthorizationHeaderParsing:
    """Test parsing of Azure SharedKey authorization headers."""

    def test_parse_shared_key_header(self):
        """Test parsing SharedKey authorization header."""
        header = "SharedKey myaccount:abc123signature=="
        
        result = parse_authorization_header(header)
        
        assert result is not None
        assert result['scheme'] == 'SharedKey'
        assert result['account'] == 'myaccount'
        assert result['signature'] == 'abc123signature=='

    def test_parse_shared_key_lite_header(self):
        """Test parsing SharedKeyLite authorization header."""
        header = "SharedKeyLite myaccount:xyz789signature=="
        
        result = parse_authorization_header(header)
        
        assert result is not None
        assert result['scheme'] == 'SharedKeyLite'
        assert result['account'] == 'myaccount'
        assert result['signature'] == 'xyz789signature=='

    def test_parse_invalid_scheme(self):
        """Test parsing header with invalid scheme."""
        header = "Bearer token123"
        
        result = parse_authorization_header(header)
        
        assert result is None

    def test_parse_malformed_header(self):
        """Test parsing malformed authorization header."""
        result = parse_authorization_header("InvalidFormat")
        assert result is None
        
        result = parse_authorization_header("SharedKey no_colon")
        assert result is None
        
        result = parse_authorization_header("")
        assert result is None
        
        result = parse_authorization_header(None)
        assert result is None


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_special_characters_in_path(self):
        """Test URL with special characters in path."""
        canonicalizer = RequestCanonicalizer()
        url = "https://myaccount.blob.core.windows.net/container/file%20with%20spaces.txt"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        # Special characters should be preserved as-is
        assert "/myaccount/container/file%20with%20spaces.txt" in canonical_resource

    def test_unicode_in_headers(self):
        """Test headers with Unicode characters."""
        canonicalizer = RequestCanonicalizer()
        headers = {
            "x-ms-meta-description": "文件说明",  # Chinese characters
            "x-ms-version": "2021-08-06"
        }
        
        canonical_headers = canonicalizer._build_canonical_headers(headers)
        
        assert "x-ms-meta-description:文件说明" in canonical_headers

    def test_very_long_url(self):
        """Test canonicalization with very long URL."""
        canonicalizer = RequestCanonicalizer()
        long_path = "/".join([f"folder{i}" for i in range(100)])
        url = f"https://myaccount.blob.core.windows.net/{long_path}/file.txt"
        
        canonical_resource = canonicalizer._build_canonical_resource(
            url, "myaccount", ServiceType.BLOB
        )
        
        assert canonical_resource.startswith("/myaccount/")
        assert "file.txt" in canonical_resource

    def test_case_sensitivity_in_values(self):
        """Test that header values maintain case sensitivity."""
        canonicalizer = RequestCanonicalizer()
        headers = {
            "x-ms-version": "2021-08-06",
            "x-ms-meta-CamelCase": "ValueWithCamelCase"
        }
        
        canonical_headers = canonicalizer._build_canonical_headers(headers)
        
        # Header names should be lowercase, but values preserve case
        assert "x-ms-meta-camelcase:ValueWithCamelCase" in canonical_headers
