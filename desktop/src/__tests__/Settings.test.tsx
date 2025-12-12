import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Settings from '../renderer/components/Settings';

describe('Settings Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders settings form', () => {
    render(<Settings />);

    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByLabelText('Host')).toBeInTheDocument();
    expect(screen.getByLabelText('Port')).toBeInTheDocument();
    expect(screen.getByLabelText('Log Level')).toBeInTheDocument();
  });

  it('loads initial config on mount', async () => {
    render(<Settings />);

    await waitFor(() => {
      expect(window.localzureAPI.getConfig).toHaveBeenCalled();
    });

    const hostInput = screen.getByLabelText('Host') as HTMLInputElement;
    const portInput = screen.getByLabelText('Port') as HTMLInputElement;

    expect(hostInput.value).toBe('127.0.0.1');
    expect(portInput.value).toBe('7071');
  });

  it('updates host when input changes', () => {
    render(<Settings />);

    const hostInput = screen.getByLabelText('Host') as HTMLInputElement;
    fireEvent.change(hostInput, { target: { value: '0.0.0.0' } });

    expect(hostInput.value).toBe('0.0.0.0');
  });

  it('updates port when input changes', () => {
    render(<Settings />);

    const portInput = screen.getByLabelText('Port') as HTMLInputElement;
    fireEvent.change(portInput, { target: { value: '8080' } });

    expect(portInput.value).toBe('8080');
  });

  it('updates log level when select changes', () => {
    render(<Settings />);

    const logLevelSelect = screen.getByLabelText('Log Level') as HTMLSelectElement;
    fireEvent.change(logLevelSelect, { target: { value: 'DEBUG' } });

    expect(logLevelSelect.value).toBe('DEBUG');
  });

  it('toggles auto-start checkbox', () => {
    render(<Settings />);

    const autoStartCheckbox = screen.getByLabelText(
      /Start LocalZure automatically/
    ) as HTMLInputElement;
    
    expect(autoStartCheckbox.checked).toBe(false);
    
    fireEvent.click(autoStartCheckbox);
    expect(autoStartCheckbox.checked).toBe(true);
  });

  it('saves settings when save button is clicked', async () => {
    render(<Settings />);

    const saveButton = screen.getByText('Save Settings');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(window.localzureAPI.updateConfig).toHaveBeenCalled();
    });
  });

  it('displays success message after saving', async () => {
    render(<Settings />);

    const saveButton = screen.getByText('Save Settings');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText('Settings saved successfully!')).toBeInTheDocument();
    });
  });

  it('displays error message on save failure', async () => {
    (window.localzureAPI.updateConfig as jest.Mock).mockResolvedValueOnce({
      success: false,
      error: 'Failed to save',
    });

    render(<Settings />);

    const saveButton = screen.getByText('Save Settings');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText('Failed to save')).toBeInTheDocument();
    });
  });

  it('shows saving state when saving', async () => {
    render(<Settings />);

    const saveButton = screen.getByText('Save Settings');
    fireEvent.click(saveButton);

    expect(screen.getByText('Saving...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Save Settings')).toBeInTheDocument();
    });
  });

  it('validates port range', () => {
    render(<Settings />);

    const portInput = screen.getByLabelText('Port') as HTMLInputElement;
    
    expect(portInput.min).toBe('1024');
    expect(portInput.max).toBe('65535');
  });

  it('displays important notes', () => {
    render(<Settings />);

    expect(screen.getByText(/Settings changes require restarting/)).toBeInTheDocument();
    expect(screen.getByText(/Make sure the port is not already in use/)).toBeInTheDocument();
    expect(screen.getByText(/Python 3.10 or higher is required/)).toBeInTheDocument();
  });
});
