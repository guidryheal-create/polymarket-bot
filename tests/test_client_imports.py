"""
Tests for Client Imports After Reorganization

Verifies that all clients can be imported correctly from their new locations.
This test belongs in the agentic_system_trading package since it tests agentic clients.
"""

import pytest


class TestClientImports:
    """Test suite for client imports after reorganization."""
    
    def test_forecasting_client_import(self):
        """Test that ForecastingClient can be imported from clients directory."""
        from core.clients.forecasting_client import (
            ForecastingClient,
            ForecastingAPIError,
            AssetNotEnabledError
        )
        
        assert ForecastingClient is not None
        assert ForecastingAPIError is not None
        assert AssetNotEnabledError is not None
    
    def test_santiment_client_import(self):
        """Test that SantimentAPIClient can be imported from clients directory."""
        from core.clients.santiment_client import (
            SantimentAPIClient,
            SantimentAPIError
        )
        
        assert SantimentAPIClient is not None
        assert SantimentAPIError is not None
    
    def test_yahoo_finance_client_import(self):
        """Test that YahooFinanceMCPClient can be imported from clients directory."""
        from core.clients.yahoo_finance_client import (
            YahooFinanceMCPClient,
            YahooFinanceMCPError
        )
        
        assert YahooFinanceMCPClient is not None
        assert YahooFinanceMCPError is not None
    
    def test_youtube_transcript_client_import(self):
        """Test that YouTubeTranscriptMCPClient can be imported from clients directory."""
        from core.clients.youtube_transcript_client import (
            YouTubeTranscriptMCPClient,
            YouTubeTranscriptMCPError
        )
        
        assert YouTubeTranscriptMCPClient is not None
        assert YouTubeTranscriptMCPError is not None
    
    def test_blockscout_client_import(self):
        """Test that BlockscoutMCPClient can be imported from clients directory."""
        from core.clients.blockscout_client import (
            BlockscoutMCPClient,
            BlockscoutMCPError
        )
        
        assert BlockscoutMCPClient is not None
        assert BlockscoutMCPError is not None
    
    def test_dex_simulator_client_import(self):
        """Test that DEXSimulatorClient can be imported from clients directory."""
        from core.clients.dex_simulator_client import (
            DEXSimulatorClient,
            DEXSimulatorError
        )
        
        assert DEXSimulatorClient is not None
        assert DEXSimulatorError is not None
    
    def test_polymarket_client_import(self):
        """Test that PolymarketClient can be imported from clients directory."""
        from core.clients.polymarket_client import (
            PolymarketClient
        )
        
        assert PolymarketClient is not None
    
    def test_clients_package_import(self):
        """Test that clients can be imported from clients package __init__."""
        from core.clients import (
            ForecastingClient,
            SantimentAPIClient,
            YahooFinanceMCPClient,
            YouTubeTranscriptMCPClient,
            BlockscoutMCPClient,
            DEXSimulatorClient,
            PolymarketClient
        )
        
        assert ForecastingClient is not None
        assert SantimentAPIClient is not None
        assert YahooFinanceMCPClient is not None
        assert YouTubeTranscriptMCPClient is not None
        assert BlockscoutMCPClient is not None
        assert DEXSimulatorClient is not None
        assert PolymarketClient is not None
    
    def test_base_client_import(self):
        """Test that base client classes can be imported."""
        from core.clients.base_client import (
            BaseHTTPClient,
            BaseMCPClient
        )
        
        assert BaseHTTPClient is not None
        assert BaseMCPClient is not None
    
    def test_client_instances_import(self):
        """Test that client instances can be imported (for backward compatibility)."""
        from core.clients.forecasting_client import (
            forecasting_client
        )
        
        from core.clients.dex_simulator_client import (
            dex_simulator_client
        )
        
        assert forecasting_client is not None
        assert dex_simulator_client is not None

