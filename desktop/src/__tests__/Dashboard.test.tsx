import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Dashboard from '../renderer/components/Dashboard';

describe('Dashboard Component', () => {
  const mockStatus = {
    status: 'running' as const,
    services: [
      {
        name: 'Service Bus',
        status: 'running' as const,
        resourceCount: 5,
        endpoint: 'http://localhost:7071/servicebus',
      },
      {
        name: 'Key Vault',
        status: 'running' as const,
        resourceCount: 3,
        endpoint: 'http://localhost:7071/keyvault',
      },
    ],
    version: '0.1.0',
    uptime: 3600,
    requestsPerSecond: 10.5,
    memoryUsage: 256.7,
  };

  const mockOnStart = jest.fn();
  const mockOnStop = jest.fn();
  const mockOnRestart = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders dashboard header', () => {
    render(
      <Dashboard
        status={mockStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    expect(screen.getByText('LocalZure Control')).toBeInTheDocument();
    expect(screen.getByText(/v0.1.0/)).toBeInTheDocument();
  });

  it('displays correct status', () => {
    render(
      <Dashboard
        status={mockStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    expect(screen.getByText('running')).toBeInTheDocument();
  });

  it('shows start button as disabled when running', () => {
    render(
      <Dashboard
        status={mockStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    const startButton = screen.getByText('▶️ Start').closest('button');
    expect(startButton).toBeDisabled();
  });

  it('shows stop button as enabled when running', () => {
    render(
      <Dashboard
        status={mockStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    const stopButton = screen.getByText('⏹️ Stop').closest('button');
    expect(stopButton).not.toBeDisabled();
  });

  it('calls onStart when start button is clicked', async () => {
    const stoppedStatus = { ...mockStatus, status: 'stopped' as const };
    
    render(
      <Dashboard
        status={stoppedStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    const startButton = screen.getByText('▶️ Start').closest('button');
    fireEvent.click(startButton!);

    await waitFor(() => {
      expect(mockOnStart).toHaveBeenCalledTimes(1);
    });
  });

  it('calls onStop when stop button is clicked', async () => {
    render(
      <Dashboard
        status={mockStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    const stopButton = screen.getByText('⏹️ Stop').closest('button');
    fireEvent.click(stopButton!);

    await waitFor(() => {
      expect(mockOnStop).toHaveBeenCalledTimes(1);
    });
  });

  it('calls onRestart when restart button is clicked', async () => {
    render(
      <Dashboard
        status={mockStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    const restartButton = screen.getByText('🔄 Restart').closest('button');
    fireEvent.click(restartButton!);

    await waitFor(() => {
      expect(mockOnRestart).toHaveBeenCalledTimes(1);
    });
  });

  it('displays quick stats when running', () => {
    render(
      <Dashboard
        status={mockStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    expect(screen.getByText('1h 0m 0s')).toBeInTheDocument(); // Uptime
    expect(screen.getByText('2/2')).toBeInTheDocument(); // Services
    expect(screen.getByText('10.5')).toBeInTheDocument(); // Requests/sec
    expect(screen.getByText('256.7 MB')).toBeInTheDocument(); // Memory
  });

  it('renders service cards', () => {
    render(
      <Dashboard
        status={mockStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    expect(screen.getByText('Service Bus')).toBeInTheDocument();
    expect(screen.getByText('Key Vault')).toBeInTheDocument();
  });

  it('displays service resource counts', () => {
    render(
      <Dashboard
        status={mockStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    // Service Bus has 5 resources
    const serviceBusCard = screen.getByText('Service Bus').closest('div');
    expect(serviceBusCard).toHaveTextContent('5');

    // Key Vault has 3 resources
    const keyVaultCard = screen.getByText('Key Vault').closest('div');
    expect(keyVaultCard).toHaveTextContent('3');
  });

  it('shows message when no services are available and stopped', () => {
    const stoppedStatus = {
      ...mockStatus,
      status: 'stopped' as const,
      services: [],
    };

    render(
      <Dashboard
        status={stoppedStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    expect(screen.getByText('Start LocalZure to see available services')).toBeInTheDocument();
  });

  it('formats uptime correctly', () => {
    const statusWithUptime = {
      ...mockStatus,
      uptime: 7325, // 2h 2m 5s
    };

    render(
      <Dashboard
        status={statusWithUptime}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    expect(screen.getByText('2h 2m 5s')).toBeInTheDocument();
  });

  it('handles starting status', () => {
    const startingStatus = {
      ...mockStatus,
      status: 'starting' as const,
    };

    render(
      <Dashboard
        status={startingStatus}
        onStart={mockOnStart}
        onStop={mockOnStop}
        onRestart={mockOnRestart}
      />
    );

    expect(screen.getByText('starting')).toBeInTheDocument();
    
    // All buttons should be disabled during starting
    const startButton = screen.getByText('▶️ Start').closest('button');
    const stopButton = screen.getByText('⏹️ Stop').closest('button');
    const restartButton = screen.getByText('🔄 Restart').closest('button');
    
    expect(startButton).toBeDisabled();
    expect(stopButton).toBeDisabled();
    expect(restartButton).toBeDisabled();
  });
});
