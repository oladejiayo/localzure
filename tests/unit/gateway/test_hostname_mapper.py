"""Tests for hostname mapping and URL rewriting."""

import pytest
from localzure.gateway.hostname_mapper import HostnameMapper, MappingResult


class TestBlobStorageMapping:
    """Test AC1: Gateway maps Azure Blob Storage URLs to localhost:10000/<account>."""

    def test_blob_url_with_container(self):
        """Test blob URL with container name."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://myaccount.blob.core.windows.net/mycontainer")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10000/myaccount/mycontainer"
        assert result.original_host == "myaccount.blob.core.windows.net"
        assert result.service_name == "blob"
        assert result.account_or_namespace == "myaccount"

    def test_blob_url_with_path(self):
        """Test blob URL with container and blob path."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://storage123.blob.core.windows.net/container/folder/file.txt")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10000/storage123/container/folder/file.txt"
        assert result.original_host == "storage123.blob.core.windows.net"
        assert result.service_name == "blob"
        assert result.account_or_namespace == "storage123"

    def test_blob_url_with_query_params(self):
        """Test blob URL with query parameters (AC7 - preserve query params)."""
        mapper = HostnameMapper()
        url = "https://test.blob.core.windows.net/container/blob?sv=2021-06-08&sr=b&sig=signature"
        result = mapper.map_url(url)
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10000/test/container/blob?sv=2021-06-08&sr=b&sig=signature"
        assert result.original_host == "test.blob.core.windows.net"

    def test_blob_url_http_scheme(self):
        """Test blob URL with HTTP scheme (not HTTPS)."""
        mapper = HostnameMapper()
        result = mapper.map_url("http://dev.blob.core.windows.net/container")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10000/dev/container"
        assert result.service_name == "blob"

    def test_blob_url_case_insensitive(self):
        """Test blob hostname matching is case-insensitive."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://MyAccount.BLOB.CORE.WINDOWS.NET/container")
        
        assert result is not None
        # Both account name and hostname are normalized to lowercase by urlparse
        assert result.mapped_url == "http://localhost:10000/myaccount/container"
        assert result.original_host == "myaccount.blob.core.windows.net"


class TestQueueStorageMapping:
    """Test AC2: Gateway maps Azure Queue URLs to localhost:10001/<account>."""

    def test_queue_url_basic(self):
        """Test queue URL mapping."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://myaccount.queue.core.windows.net/myqueue")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10001/myaccount/myqueue"
        assert result.original_host == "myaccount.queue.core.windows.net"
        assert result.service_name == "queue"
        assert result.account_or_namespace == "myaccount"

    def test_queue_url_with_messages_path(self):
        """Test queue URL with messages endpoint."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://storage.queue.core.windows.net/queue1/messages")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10001/storage/queue1/messages"
        assert result.service_name == "queue"

    def test_queue_url_with_query_params(self):
        """Test queue URL with query parameters (AC7)."""
        mapper = HostnameMapper()
        url = "https://test.queue.core.windows.net/queue?numofmessages=5&visibilitytimeout=30"
        result = mapper.map_url(url)
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10001/test/queue?numofmessages=5&visibilitytimeout=30"


class TestTableStorageMapping:
    """Test AC3: Gateway maps Azure Table URLs to localhost:10002/<account>."""

    def test_table_url_basic(self):
        """Test table URL mapping."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://myaccount.table.core.windows.net/mytable")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10002/myaccount/mytable"
        assert result.original_host == "myaccount.table.core.windows.net"
        assert result.service_name == "table"
        assert result.account_or_namespace == "myaccount"

    def test_table_url_with_query(self):
        """Test table URL with OData query (AC7)."""
        mapper = HostnameMapper()
        url = "https://storage.table.core.windows.net/Customers()?$filter=PartitionKey%20eq%20'USA'"
        result = mapper.map_url(url)
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10002/storage/Customers()?$filter=PartitionKey%20eq%20'USA'"
        assert result.service_name == "table"


class TestServiceBusMapping:
    """Test AC4: Gateway maps Service Bus URLs to localhost:5672."""

    def test_servicebus_url_basic(self):
        """Test Service Bus URL mapping."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://mynamespace.servicebus.windows.net/myqueue")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:5672/myqueue"
        assert result.original_host == "mynamespace.servicebus.windows.net"
        assert result.service_name == "servicebus"
        assert result.account_or_namespace == "mynamespace"

    def test_servicebus_url_with_topic(self):
        """Test Service Bus URL with topic and subscription."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://ns1.servicebus.windows.net/topic1/subscriptions/sub1/messages")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:5672/topic1/subscriptions/sub1/messages"
        assert result.service_name == "servicebus"

    def test_servicebus_url_with_query(self):
        """Test Service Bus URL with query parameters (AC7)."""
        mapper = HostnameMapper()
        url = "https://test.servicebus.windows.net/queue?timeout=60"
        result = mapper.map_url(url)
        
        assert result is not None
        assert result.mapped_url == "http://localhost:5672/queue?timeout=60"


class TestKeyVaultMapping:
    """Test AC5: Gateway maps Key Vault URLs to localhost:8200/<vault>."""

    def test_keyvault_url_basic(self):
        """Test Key Vault URL mapping."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://myvault.vault.azure.net/secrets/mysecret")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:8200/myvault/secrets/mysecret"
        assert result.original_host == "myvault.vault.azure.net"
        assert result.service_name == "keyvault"
        assert result.account_or_namespace == "myvault"

    def test_keyvault_url_with_version(self):
        """Test Key Vault URL with secret version."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://vault1.vault.azure.net/secrets/secret1/abc123def456")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:8200/vault1/secrets/secret1/abc123def456"
        assert result.service_name == "keyvault"

    def test_keyvault_url_with_query(self):
        """Test Key Vault URL with API version query (AC7)."""
        mapper = HostnameMapper()
        url = "https://test.vault.azure.net/keys/mykey?api-version=7.3"
        result = mapper.map_url(url)
        
        assert result is not None
        assert result.mapped_url == "http://localhost:8200/test/keys/mykey?api-version=7.3"


class TestCosmosDBMapping:
    """Test AC6: Gateway maps Cosmos DB URLs to localhost:8081/<account>."""

    def test_cosmosdb_url_basic(self):
        """Test Cosmos DB URL mapping."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://myaccount.documents.azure.com/dbs/mydb")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:8081/myaccount/dbs/mydb"
        assert result.original_host == "myaccount.documents.azure.com"
        assert result.service_name == "cosmosdb"
        assert result.account_or_namespace == "myaccount"

    def test_cosmosdb_url_with_collection(self):
        """Test Cosmos DB URL with database and collection."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://cosmos1.documents.azure.com/dbs/db1/colls/coll1/docs")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:8081/cosmos1/dbs/db1/colls/coll1/docs"
        assert result.service_name == "cosmosdb"

    def test_cosmosdb_url_with_query(self):
        """Test Cosmos DB URL with query parameters (AC7)."""
        mapper = HostnameMapper()
        url = "https://test.documents.azure.com/dbs/db1/colls/coll1?maxItemCount=100"
        result = mapper.map_url(url)
        
        assert result is not None
        assert result.mapped_url == "http://localhost:8081/test/dbs/db1/colls/coll1?maxItemCount=100"


class TestPathAndQueryPreservation:
    """Test AC7: URL path and query parameters are preserved during rewriting."""

    def test_complex_path_preserved(self):
        """Test complex multi-level path is preserved."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://test.blob.core.windows.net/container/folder1/folder2/folder3/file.txt")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10000/test/container/folder1/folder2/folder3/file.txt"

    def test_multiple_query_params_preserved(self):
        """Test multiple query parameters are preserved."""
        mapper = HostnameMapper()
        url = "https://test.blob.core.windows.net/container/blob?sv=2021-06-08&sr=b&sig=xyz&st=2023-01-01&se=2023-12-31"
        result = mapper.map_url(url)
        
        assert result is not None
        assert "sv=2021-06-08" in result.mapped_url
        assert "sr=b" in result.mapped_url
        assert "sig=xyz" in result.mapped_url
        assert "st=2023-01-01" in result.mapped_url
        assert "se=2023-12-31" in result.mapped_url

    def test_special_characters_in_path(self):
        """Test special characters in path are preserved."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://test.blob.core.windows.net/container/file%20with%20spaces.txt")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10000/test/container/file%20with%20spaces.txt"

    def test_empty_path_handled(self):
        """Test URL with no path after hostname."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://test.blob.core.windows.net")
        
        assert result is not None
        # Empty path is normalized to "/" by urlparse
        assert result.mapped_url == "http://localhost:10000/test/"

    def test_root_path_handled(self):
        """Test URL with root path only."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://test.blob.core.windows.net/")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10000/test/"

    def test_fragment_preserved(self):
        """Test URL fragment is preserved."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://test.blob.core.windows.net/container/blob#section1")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10000/test/container/blob#section1"


class TestCustomMappings:
    """Test custom hostname mappings configuration."""

    def test_custom_mapping_exact_match(self):
        """Test custom hostname mapping with exact match."""
        mapper = HostnameMapper(custom_mappings={"custom.domain.com": "http://localhost:9000"})
        result = mapper.map_url("https://custom.domain.com/api/endpoint")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:9000/api/endpoint"
        assert result.original_host == "custom.domain.com"
        assert result.service_name == "custom"

    def test_add_custom_mapping(self):
        """Test adding custom mapping dynamically."""
        mapper = HostnameMapper()
        mapper.add_custom_mapping("custom.blob.example.com", "http://localhost:11000")
        
        result = mapper.map_url("https://custom.blob.example.com/container")
        assert result is not None
        assert result.mapped_url == "http://localhost:11000/container"

    def test_remove_custom_mapping(self):
        """Test removing custom mapping."""
        mapper = HostnameMapper(custom_mappings={"custom.domain.com": "http://localhost:9000"})
        
        # Verify it works initially
        result = mapper.map_url("https://custom.domain.com/test")
        assert result is not None
        
        # Remove and verify it no longer maps
        removed = mapper.remove_custom_mapping("custom.domain.com")
        assert removed is True
        
        result = mapper.map_url("https://custom.domain.com/test")
        assert result is None

    def test_custom_mapping_takes_precedence(self):
        """Test custom mappings take precedence over default patterns."""
        # Override default blob mapping
        mapper = HostnameMapper(custom_mappings={"test.blob.core.windows.net": "http://localhost:9999"})
        result = mapper.map_url("https://test.blob.core.windows.net/container")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:9999/container"
        assert result.service_name == "custom"


class TestOriginalHostHeader:
    """Test X-Original-Host header preservation."""

    def test_get_original_host_header(self):
        """Test generating X-Original-Host header."""
        mapper = HostnameMapper()
        headers = mapper.get_original_host_header("myaccount.blob.core.windows.net")
        
        assert headers == {"X-Original-Host": "myaccount.blob.core.windows.net"}

    def test_original_host_in_mapping_result(self):
        """Test original host is preserved in mapping result."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://test.blob.core.windows.net/container")
        
        assert result is not None
        headers = mapper.get_original_host_header(result.original_host)
        assert headers["X-Original-Host"] == "test.blob.core.windows.net"


class TestUnsupportedURLs:
    """Test handling of URLs that don't match any pattern."""

    def test_non_azure_url_returns_none(self):
        """Test non-Azure URL returns None."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://example.com/path")
        
        assert result is None

    def test_partial_azure_url_returns_none(self):
        """Test partial Azure-like URL returns None."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://blob.core.windows.net/container")  # Missing account
        
        assert result is None

    def test_malformed_url_returns_none(self):
        """Test malformed URL returns None."""
        mapper = HostnameMapper()
        result = mapper.map_url("not-a-valid-url")
        
        assert result is None


class TestServiceInfo:
    """Test service information and listing."""

    def test_list_supported_services(self):
        """Test listing all supported services."""
        mapper = HostnameMapper()
        services = mapper.list_supported_services()
        
        assert "blob" in services
        assert "queue" in services
        assert "table" in services
        assert "servicebus" in services
        assert "keyvault" in services
        assert "cosmosdb" in services
        assert len(services) == 6

    def test_get_service_info_blob(self):
        """Test getting service info for blob storage."""
        mapper = HostnameMapper()
        info = mapper.get_service_info("blob")
        
        assert info is not None
        assert info["service_name"] == "blob"
        assert info["local_base"] == "http://localhost:10000"
        # Pattern is a regex string with escaped characters
        assert "blob" in info["pattern"] and "core" in info["pattern"] and "windows" in info["pattern"]

    def test_get_service_info_unknown(self):
        """Test getting service info for unknown service returns None."""
        mapper = HostnameMapper()
        info = mapper.get_service_info("unknown")
        
        assert info is None


class TestAccountNameVariations:
    """Test various account name formats."""

    def test_account_with_hyphens(self):
        """Test account name with hyphens."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://my-storage-account.blob.core.windows.net/container")
        
        assert result is not None
        assert result.mapped_url == "http://localhost:10000/my-storage-account/container"
        assert result.account_or_namespace == "my-storage-account"

    def test_account_with_numbers(self):
        """Test account name with numbers."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://storage123456.blob.core.windows.net/container")
        
        assert result is not None
        assert result.account_or_namespace == "storage123456"

    def test_short_account_name(self):
        """Test short account name (minimum length)."""
        mapper = HostnameMapper()
        result = mapper.map_url("https://abc.blob.core.windows.net/container")
        
        assert result is not None
        assert result.account_or_namespace == "abc"

    def test_long_account_name(self):
        """Test long account name."""
        mapper = HostnameMapper()
        long_name = "a" * 24  # Azure storage accounts can be up to 24 chars
        result = mapper.map_url(f"https://{long_name}.blob.core.windows.net/container")
        
        assert result is not None
        assert result.account_or_namespace == long_name
