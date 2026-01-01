"""
Docker container helpers for MCP server communication
"""
import subprocess
import json
from typing import Optional
from reasoner_pod.utils.logging import get_logger

logger = get_logger(__name__)


class DockerHelper:
    """Helper class for Docker operations"""
    
    @staticmethod
    def is_container_running(container_name: str) -> bool:
        """
        Check if a Docker container is running
        
        Args:
            container_name: Name of the container
            
        Returns:
            True if container is running, False otherwise
        """
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            return container_name in result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Failed to check container status for {container_name}: {e}")
            return False
    
    @staticmethod
    def get_container_info(container_name: str) -> Optional[dict]:
        """
        Get container inspection info
        
        Args:
            container_name: Name of the container
            
        Returns:
            Container info dict or None if not found
        """
        try:
            result = subprocess.run(
                ["docker", "inspect", container_name],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            info = json.loads(result.stdout)
            return info[0] if info else None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to get container info for {container_name}: {e}")
            return None
    
    @staticmethod
    def get_container_env(container_name: str) -> dict[str, str]:
        """
        Get environment variables from a container
        
        Args:
            container_name: Name of the container
            
        Returns:
            Dictionary of environment variables
        """
        info = DockerHelper.get_container_info(container_name)
        if not info:
            return {}
        
        env_list = info.get("Config", {}).get("Env", [])
        env_dict = {}
        
        for env_var in env_list:
            if "=" in env_var:
                key, value = env_var.split("=", 1)
                env_dict[key] = value
        
        return env_dict
    
    @staticmethod
    def get_mcp_server_status() -> dict[str, bool]:
        """
        Check status of MCP servers via OpenCode
        
        Note: MCP servers are now managed by OpenCode, not Docker directly.
        This method is deprecated - use OpenCode /mcp endpoint instead.
        
        Returns:
            Empty dictionary (deprecated)
        """
        # MCP servers are now ephemeral and managed by OpenCode
        return {}


