interface SidebarProps {
  currentView: 'dashboard' | 'blob' | 'servicebus' | 'keyvault' | 'queue' | 'table' | 'cosmos' | 'settings' | 'logs';
  onViewChange: (view: 'dashboard' | 'blob' | 'servicebus' | 'keyvault' | 'queue' | 'table' | 'cosmos' | 'settings' | 'logs') => void;
}

interface NavItem {
  id: 'dashboard' | 'blob' | 'servicebus' | 'keyvault' | 'queue' | 'table' | 'cosmos' | 'settings' | 'logs';
  label: string;
  icon: string;
}

const navItems: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'blob', label: 'Blob Storage', icon: '📦' },
  { id: 'servicebus', label: 'Service Bus', icon: '📮' },
  { id: 'keyvault', label: 'Key Vault', icon: '🔐' },
  { id: 'queue', label: 'Queue Storage', icon: '📝' },
  { id: 'table', label: 'Table Storage', icon: '📋' },
  { id: 'cosmos', label: 'Cosmos DB', icon: '🌐' },
  // { id: 'logs', label: 'Logs', icon: '📜' }, // Hidden - logs are in terminal where localzure runs
  { id: 'settings', label: 'Settings', icon: '⚙️' },
];

function Sidebar({ currentView, onViewChange }: SidebarProps) {
  return (
    <aside className="w-64 bg-gray-900 text-white flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-gray-700">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <span className="text-3xl">🌀</span>
          <span>LocalZure</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">Azure Cloud Emulator</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {navItems.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => onViewChange(item.id)}
                className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-colors ${
                  currentView === item.id
                    ? 'bg-azure-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`}
              >
                <span className="text-xl">{item.icon}</span>
                <span className="font-medium">{item.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-700">
        <div className="text-xs text-gray-400">
          <p>Version 0.1.0</p>
          <p className="mt-1">© 2025 LocalZure Contributors</p>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
