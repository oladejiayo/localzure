import { render, screen, fireEvent } from '@testing-library/react';
import Sidebar from '../renderer/components/Sidebar';

describe('Sidebar Component', () => {
  const mockOnViewChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders LocalZure logo and title', () => {
    render(<Sidebar currentView="dashboard" onViewChange={mockOnViewChange} />);

    expect(screen.getByText('LocalZure')).toBeInTheDocument();
    expect(screen.getByText('Azure Cloud Emulator')).toBeInTheDocument();
  });

  it('renders all navigation items', () => {
    render(<Sidebar currentView="dashboard" onViewChange={mockOnViewChange} />);

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Logs')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('highlights the current view', () => {
    render(<Sidebar currentView="dashboard" onViewChange={mockOnViewChange} />);

    const dashboardButton = screen.getByText('Dashboard').closest('button');
    const logsButton = screen.getByText('Logs').closest('button');

    expect(dashboardButton).toHaveClass('bg-azure-600');
    expect(logsButton).not.toHaveClass('bg-azure-600');
  });

  it('calls onViewChange when a navigation item is clicked', () => {
    render(<Sidebar currentView="dashboard" onViewChange={mockOnViewChange} />);

    const logsButton = screen.getByText('Logs').closest('button');
    fireEvent.click(logsButton!);

    expect(mockOnViewChange).toHaveBeenCalledWith('logs');
  });

  it('displays version information', () => {
    render(<Sidebar currentView="dashboard" onViewChange={mockOnViewChange} />);

    expect(screen.getByText('Version 0.1.0')).toBeInTheDocument();
    expect(screen.getByText('© 2025 LocalZure Contributors')).toBeInTheDocument();
  });

  it('switches view correctly', () => {
    const { rerender } = render(
      <Sidebar currentView="dashboard" onViewChange={mockOnViewChange} />
    );

    let dashboardButton = screen.getByText('Dashboard').closest('button');
    let settingsButton = screen.getByText('Settings').closest('button');

    expect(dashboardButton).toHaveClass('bg-azure-600');
    expect(settingsButton).not.toHaveClass('bg-azure-600');

    // Simulate view change
    rerender(<Sidebar currentView="settings" onViewChange={mockOnViewChange} />);

    dashboardButton = screen.getByText('Dashboard').closest('button');
    settingsButton = screen.getByText('Settings').closest('button');

    expect(dashboardButton).not.toHaveClass('bg-azure-600');
    expect(settingsButton).toHaveClass('bg-azure-600');
  });
});
