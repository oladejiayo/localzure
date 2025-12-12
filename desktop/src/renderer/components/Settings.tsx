import { useState, useEffect } from 'react';

interface Config {
  port: number;
  host: string;
  logLevel: string;
  autoStart: boolean;
  pythonPath?: string;
}

function Settings() {
  const [config, setConfig] = useState<Config>({
    port: 7071,
    host: '127.0.0.1',
    logLevel: 'INFO',
    autoStart: false,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    // Load config on mount
    window.localzureAPI.getConfig().then((loadedConfig) => {
      setConfig(loadedConfig);
    });
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage(null);

    try {
      const result = await window.localzureAPI.updateConfig(config);
      if (result.success) {
        setSaveMessage({ type: 'success', text: 'Settings saved successfully!' });
      } else {
        setSaveMessage({ type: 'error', text: result.error || 'Failed to save settings' });
      }
    } catch (error) {
      setSaveMessage({ type: 'error', text: 'Failed to save settings' });
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveMessage(null), 3000);
    }
  };

  return (
    <div className="p-8 max-w-4xl">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Settings</h2>

        <div className="space-y-6">
          {/* Server Settings */}
          <section>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Server Configuration</h3>
            
            <div className="space-y-4">
              <div>
                <label htmlFor="host" className="block text-sm font-medium text-gray-700 mb-2">
                  Host
                </label>
                <input
                  id="host"
                  type="text"
                  value={config.host}
                  onChange={(e) => setConfig({ ...config, host: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-azure-500 focus:border-transparent"
                  placeholder="127.0.0.1"
                />
                <p className="mt-1 text-xs text-gray-500">
                  The host address LocalZure will bind to
                </p>
              </div>

              <div>
                <label htmlFor="port" className="block text-sm font-medium text-gray-700 mb-2">
                  Port
                </label>
                <input
                  id="port"
                  type="number"
                  value={config.port}
                  onChange={(e) => setConfig({ ...config, port: parseInt(e.target.value) })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-azure-500 focus:border-transparent"
                  placeholder="7071"
                  min="1024"
                  max="65535"
                />
                <p className="mt-1 text-xs text-gray-500">
                  The port number LocalZure will listen on (1024-65535)
                </p>
              </div>

              <div>
                <label htmlFor="logLevel" className="block text-sm font-medium text-gray-700 mb-2">
                  Log Level
                </label>
                <select
                  id="logLevel"
                  value={config.logLevel}
                  onChange={(e) => setConfig({ ...config, logLevel: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-azure-500 focus:border-transparent"
                >
                  <option value="DEBUG">DEBUG</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  Minimum log level to display
                </p>
              </div>
            </div>
          </section>

          {/* Application Settings */}
          <section className="pt-6 border-t">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Application Settings</h3>
            
            <div className="space-y-4">
              <div className="flex items-center">
                <input
                  id="autoStart"
                  type="checkbox"
                  checked={config.autoStart}
                  onChange={(e) => setConfig({ ...config, autoStart: e.target.checked })}
                  className="w-4 h-4 text-azure-600 border-gray-300 rounded focus:ring-azure-500"
                />
                <label htmlFor="autoStart" className="ml-3 text-sm text-gray-700">
                  Start LocalZure automatically when application launches
                </label>
              </div>

              <div>
                <label htmlFor="pythonPath" className="block text-sm font-medium text-gray-700 mb-2">
                  Python Path (Optional)
                </label>
                <input
                  id="pythonPath"
                  type="text"
                  value={config.pythonPath || ''}
                  onChange={(e) => setConfig({ ...config, pythonPath: e.target.value || undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-azure-500 focus:border-transparent"
                  placeholder="Auto-detect"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Path to Python executable. Leave empty to auto-detect.
                </p>
              </div>
            </div>
          </section>

          {/* Save Button */}
          <div className="pt-6 border-t flex items-center justify-between">
            <div>
              {saveMessage && (
                <p
                  className={`text-sm ${
                    saveMessage.type === 'success' ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {saveMessage.text}
                </p>
              )}
            </div>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-6 py-3 bg-azure-600 text-white rounded-lg font-medium hover:bg-azure-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {isSaving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex gap-3">
            <span className="text-2xl">ℹ️</span>
            <div className="text-sm text-blue-900">
              <p className="font-medium mb-1">Important Notes:</p>
              <ul className="list-disc list-inside space-y-1 text-blue-800">
                <li>Settings changes require restarting LocalZure to take effect</li>
                <li>Make sure the port is not already in use by another application</li>
                <li>Python 3.10 or higher is required to run LocalZure</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Settings;
