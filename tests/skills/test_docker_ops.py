import pytest
from unittest.mock import MagicMock, patch
from nanobot.skills.docker_ops.tool import DockerOpsTool
import docker

@pytest.fixture
def mock_docker():
    with patch("docker.from_env") as mock:
        yield mock

@pytest.fixture
def tool(mock_docker):
    return DockerOpsTool()

def test_list_containers(tool, mock_docker):
    """Test listing containers."""
    mock_client = mock_docker.return_value
    mock_container = MagicMock()
    mock_container.short_id = "123456"
    mock_container.name = "test-worker"
    mock_container.status = "running"
    mock_container.image.tags = ["nanobot-worker:latest"]
    
    mock_client.containers.list.return_value = [mock_container]
    
    result = tool.execute(action="list_containers")
    
    mock_client.containers.list.assert_called_once()
    call_kwargs = mock_client.containers.list.call_args[1]
    assert call_kwargs['filters'] == {"label": ["com.mspbots.nanobot=true"]}
    
    assert len(result) == 1
    assert result[0]["name"] == "test-worker"

def test_spawn_container_allowed_image(tool, mock_docker):
    """Test spawning a container with an allowed image."""
    mock_client = mock_docker.return_value
    mock_container = MagicMock()
    mock_container.short_id = "new123"
    mock_container.name = "new-worker"
    
    mock_client.containers.run.return_value = mock_container
    
    result = tool.execute(
        action="spawn_container", 
        name="new-worker", 
        image="nanobot-worker:latest", 
        env_vars={"FOO": "BAR"}
    )
    
    mock_client.containers.run.assert_called_once()
    call_args = mock_client.containers.run.call_args
    assert call_args[0][0] == "nanobot-worker:latest"
    assert call_args[1]["name"] == "new-worker"
    assert call_args[1]["environment"] == {"FOO": "BAR"}
    assert call_args[1]["labels"] == {"com.mspbots.nanobot": "true"}
    assert call_args[1]["detach"] is True
    
    assert result["name"] == "new-worker"

def test_spawn_container_disallowed_image(tool):
    """Test spawning a container with a disallowed image throws error."""
    with pytest.raises(ValueError) as excinfo:
        tool.execute(
            action="spawn_container", 
            name="bad-actor", 
            image="ubuntu:latest"
        )
    assert "not allowed" in str(excinfo.value)

def test_stop_container_success(tool, mock_docker):
    """Test stopping a managed container."""
    mock_client = mock_docker.return_value
    mock_container = MagicMock()
    mock_container.labels = {"com.mspbots.nanobot": "true"}
    
    mock_client.containers.get.return_value = mock_container
    
    tool.execute(action="stop_container", name="worker-1")
    
    mock_client.containers.get.assert_called_with("worker-1")
    mock_container.stop.assert_called_once()

def test_stop_container_not_managed(tool, mock_docker):
    """Test stopping an unmanaged container throws PermissionError."""
    mock_client = mock_docker.return_value
    mock_container = MagicMock()
    mock_container.labels = {} # No nanobot label
    
    mock_client.containers.get.return_value = mock_container
    
    with pytest.raises(PermissionError) as excinfo:
        tool.execute(action="stop_container", name="random-container")
    
    assert "Access denied" in str(excinfo.value)
    mock_container.stop.assert_not_called()

def test_stop_container_self_preservation(tool):
    """Test stopping 'nanobot-sol' throws ValueError."""
    with pytest.raises(ValueError) as excinfo:
        tool.execute(action="stop_container", name="nanobot-sol")
    
    assert "Self-preservation" in str(excinfo.value)

def test_get_logs(tool, mock_docker):
    """Test getting logs from a managed container."""
    mock_client = mock_docker.return_value
    mock_container = MagicMock()
    mock_container.labels = {"com.mspbots.nanobot": "true"}
    mock_container.logs.return_value = b"log line 1\nlog line 2"
    
    mock_client.containers.get.return_value = mock_container
    
    logs = tool.execute(action="get_logs", name="worker-1", tail=50)
    
    mock_client.containers.get.assert_called_with("worker-1")
    mock_container.logs.assert_called_with(tail=50)
    assert logs == "log line 1\nlog line 2"

def test_inspect_container(tool, mock_docker):
    """Test inspecting a managed container."""
    mock_client = mock_docker.return_value
    mock_container = MagicMock()
    mock_container.labels = {"com.mspbots.nanobot": "true"}
    mock_container.attrs = {"State": "running", "Id": "123"}
    
    mock_client.containers.get.return_value = mock_container
    
    info = tool.execute(action="inspect_container", name="worker-1")
    
    assert info == {"State": "running", "Id": "123"}
