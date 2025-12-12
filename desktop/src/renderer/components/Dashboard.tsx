interface SystemStatus {
  status: 'running' | 'stopped' | 'starting' | 'stopping' | 'error';
  services: ServiceStatus[];
  version: string;
  uptime?: number;
  requestsPerSecond?: number;
  memoryUsage?: number;
}

interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'error';
  resourceCount?: number;
  endpoint?: string;
}

interface DashboardProps {
  status: SystemStatus;
  onStart: () => void;
  onStop: () => void;
  onRestart: () => void;
  onNavigateToService?: (serviceName: string) => void;
}

function Dashboard({ status, onStart, onStop, onRestart, onNavigateToService }: DashboardProps) {
  const isRunning = status.status === 'running';
  const isStarting = status.status === 'starting';
  const isStopping = status.status === 'stopping';
  const isTransitioning = isStarting || isStopping;

  const formatUptime = (seconds?: number): string => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours}h ${minutes}m ${secs}s`;
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'running':
        return 'text-emerald-600 bg-emerald-100';
      case 'stopped':
        return 'text-rose-600 bg-rose-100';
      case 'starting':
      case 'stopping':
        return 'text-amber-600 bg-amber-100';
      case 'error':
        return 'text-red-700 bg-red-200';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 p-8">
      {/* Header with Glassmorphism */}
      <div className="backdrop-blur-xl bg-white/80 border border-white/20 rounded-2xl shadow-2xl p-8 mb-8 hover:shadow-3xl transition-all duration-300">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            {/* Premium Logo */}
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl blur-xl opacity-50 animate-pulse"></div>
              <div className="relative bg-gradient-to-br from-blue-500 to-indigo-600 p-4 rounded-2xl shadow-lg">
                <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                </svg>
              </div>
            </div>
            
            <div>
              <h2 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                LocalZure Enterprise
              </h2>
              <div className="flex items-center gap-3 mt-2">
                <div className="flex items-center gap-2">
                  <div className={`w-2.5 h-2.5 rounded-full ${isRunning ? 'bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse' : 'bg-slate-400'}`}></div>
                  <span className="text-sm font-medium text-slate-700 capitalize">{status.status}</span>
                </div>
                <span className="text-slate-400">•</span>
                <span className="text-sm font-mono text-slate-500 bg-slate-100 px-3 py-1 rounded-full">v{status.version}</span>
              </div>
            </div>
          </div>

          {/* Premium Action Buttons */}
          <div className="flex gap-3">
            <button
              onClick={onStart}
              disabled={isRunning || isTransitioning}
              className="group relative px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-lg font-medium text-sm shadow-lg shadow-emerald-500/30 hover:shadow-xl hover:shadow-emerald-500/40 hover:scale-105 disabled:from-slate-300 disabled:to-slate-400 disabled:shadow-none disabled:cursor-not-allowed disabled:hover:scale-100 transition-all duration-200"
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                </svg>
                Start
              </span>
            </button>
            <button
              onClick={onStop}
              disabled={!isRunning || isTransitioning}
              className="group relative px-4 py-2 bg-gradient-to-r from-rose-500 to-pink-600 text-white rounded-lg font-medium text-sm shadow-lg shadow-rose-500/30 hover:shadow-xl hover:shadow-rose-500/40 hover:scale-105 disabled:from-slate-300 disabled:to-slate-400 disabled:shadow-none disabled:cursor-not-allowed disabled:hover:scale-100 transition-all duration-200"
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
                </svg>
                Stop
              </span>
            </button>
            <button
              onClick={onRestart}
              disabled={!isRunning || isTransitioning}
              className="group relative px-4 py-2 bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-lg font-medium text-sm shadow-lg shadow-blue-500/30 hover:shadow-xl hover:shadow-blue-500/40 hover:scale-105 disabled:from-slate-300 disabled:to-slate-400 disabled:shadow-none disabled:cursor-not-allowed disabled:hover:scale-100 transition-all duration-200"
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 group-hover:rotate-180 transition-transform duration-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
                </svg>
                Restart
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Premium Stats Grid */}
      {isRunning && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard
            icon={
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            label="System Uptime"
            value={formatUptime(status.uptime)}
            color="blue"
            trend="+2.5%"
          />
          <StatCard
            icon={
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            label="Active Services"
            value={`${status.services.filter((s) => s.status === 'running').length}/${status.services.length}`}
            color="green"
            trend="All Healthy"
          />
          <StatCard
            icon={
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            }
            label="Requests/sec"
            value={status.requestsPerSecond?.toFixed(1) || '0.0'}
            color="purple"
            trend="+12.3%"
          />
          <StatCard
            icon={
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
            }
            label="Memory Usage"
            value={`${status.memoryUsage?.toFixed(1) || '0.0'} MB`}
            color="orange"
            trend="Optimal"
          />
        </div>
      )}

      {/* Services Section */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-2xl font-bold text-slate-800">Azure Services</h3>
          <span className="text-sm text-slate-500 bg-white/60 backdrop-blur px-4 py-2 rounded-full font-medium">
            {status.services.length} Services Available
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {status.services.length > 0 ? (
            status.services.map((service) => (
              <ServiceCard key={service.name} service={service} onManage={onNavigateToService} />
            ))
          ) : (
            <div className="col-span-full backdrop-blur-xl bg-white/60 border border-white/20 rounded-2xl shadow-xl p-12 text-center">
              <div className="text-6xl mb-4 opacity-50">☁️</div>
              <p className="text-slate-600 font-medium">
                {isRunning
                  ? 'No services available'
                  : 'Start LocalZure to see available services'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Recent Activity with Timeline */}
      {isRunning && (
        <div>
          <h3 className="text-2xl font-bold text-slate-800 mb-6">Recent Activity</h3>
          <div className="backdrop-blur-xl bg-white/80 border border-white/20 rounded-2xl shadow-xl p-8">
            <div className="space-y-4">
              <ActivityItem
                icon={
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-lg">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                }
                message="Service Bus queue created: my-queue"
                time="2 minutes ago"
                type="success"
              />
              <ActivityItem
                icon={
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center shadow-lg">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                    </svg>
                  </div>
                }
                message="Key Vault secret stored: connection-string"
                time="5 minutes ago"
                type="info"
              />
              <ActivityItem
                icon={
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-400 to-pink-500 flex items-center justify-center shadow-lg">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                    </svg>
                  </div>
                }
                message="Blob container created: uploads"
                time="8 minutes ago"
                type="info"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: 'blue' | 'green' | 'purple' | 'orange';
  trend?: string;
}

function StatCard({ icon, label, value, color, trend }: StatCardProps) {
  const colorClasses = {
    blue: {
      gradient: 'from-blue-500 to-indigo-600',
      bg: 'bg-blue-50',
      text: 'text-blue-600',
      shadow: 'shadow-blue-500/20'
    },
    green: {
      gradient: 'from-emerald-500 to-teal-600',
      bg: 'bg-emerald-50',
      text: 'text-emerald-600',
      shadow: 'shadow-emerald-500/20'
    },
    purple: {
      gradient: 'from-purple-500 to-pink-600',
      bg: 'bg-purple-50',
      text: 'text-purple-600',
      shadow: 'shadow-purple-500/20'
    },
    orange: {
      gradient: 'from-orange-500 to-red-600',
      bg: 'bg-orange-50',
      text: 'text-orange-600',
      shadow: 'shadow-orange-500/20'
    },
  };

  const classes = colorClasses[color];

  return (
    <div className="group relative backdrop-blur-xl bg-white/80 border border-white/20 rounded-2xl shadow-xl hover:shadow-2xl transition-all duration-300 overflow-hidden">
      {/* Animated background gradient */}
      <div className={`absolute inset-0 bg-gradient-to-br ${classes.gradient} opacity-0 group-hover:opacity-5 transition-opacity duration-300`}></div>
      
      <div className="relative p-6">
        <div className="flex items-start justify-between mb-4">
          <div className={`p-3 rounded-xl bg-gradient-to-br ${classes.gradient} ${classes.shadow} shadow-lg transform group-hover:scale-110 transition-transform duration-300`}>
            <div className="text-white">
              {icon}
            </div>
          </div>
          {trend && (
            <span className={`text-xs font-semibold ${classes.text} ${classes.bg} px-3 py-1 rounded-full`}>
              {trend}
            </span>
          )}
        </div>
        <div>
          <p className="text-sm font-medium text-slate-500 mb-1">{label}</p>
          <p className="text-3xl font-bold text-slate-800">{value}</p>
        </div>
      </div>
      
      {/* Bottom accent line */}
      <div className={`h-1 bg-gradient-to-r ${classes.gradient}`}></div>
    </div>
  );
}

interface ServiceCardProps {
  service: ServiceStatus;
  onManage?: (serviceName: string) => void;
}

function ServiceCard({ service, onManage }: ServiceCardProps) {
  const isRunning = service.status === 'running';
  
  const handleManageClick = () => {
    if (isRunning && onManage) {
      onManage(service.name);
    }
  };
  
  const serviceIcons = {
    'Service Bus': {
      gradient: 'from-blue-500 to-cyan-600',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
      )
    },
    'Key Vault': {
      gradient: 'from-purple-500 to-pink-600',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
        </svg>
      )
    },
    'Blob Storage': {
      gradient: 'from-emerald-500 to-teal-600',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
        </svg>
      )
    },
    'Queue Storage': {
      gradient: 'from-orange-500 to-red-600',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
      )
    },
    'Table Storage': {
      gradient: 'from-indigo-500 to-purple-600',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )
    },
    'Cosmos DB': {
      gradient: 'from-violet-500 to-fuchsia-600',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
        </svg>
      )
    }
  };

  const serviceInfo = serviceIcons[service.name as keyof typeof serviceIcons] || serviceIcons['Service Bus'];
  
  return (
    <div className="group relative backdrop-blur-xl bg-white/80 border border-white/20 rounded-2xl shadow-xl hover:shadow-2xl transition-all duration-300 overflow-hidden">
      {/* Animated background gradient on hover */}
      <div className={`absolute inset-0 bg-gradient-to-br ${serviceInfo.gradient} opacity-0 group-hover:opacity-10 transition-opacity duration-300`}></div>
      
      <div className="relative p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl bg-gradient-to-br ${serviceInfo.gradient} shadow-lg text-white transform group-hover:scale-110 group-hover:rotate-3 transition-all duration-300`}>
              {serviceInfo.icon}
            </div>
            <div>
              <h4 className="text-lg font-bold text-slate-800 mb-1">{service.name}</h4>
              <div className="flex items-center gap-2">
                {isRunning ? (
                  <>
                    <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse"></div>
                    <span className="text-xs font-semibold text-emerald-600">Active</span>
                  </>
                ) : (
                  <>
                    <div className="w-2 h-2 rounded-full bg-rose-500"></div>
                    <span className="text-xs font-semibold text-rose-600">Inactive</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
        
        {/* Stats */}
        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
            <div className="flex items-center gap-2 text-slate-600">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
              </svg>
              <span className="text-sm font-medium">Resources</span>
            </div>
            <span className="text-lg font-bold text-slate-800">{service.resourceCount || 0}</span>
          </div>
          
          {service.endpoint && (
            <div className="p-3 bg-slate-50 rounded-xl">
              <div className="flex items-center gap-2 text-slate-600 mb-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                <span className="text-xs font-medium">Endpoint</span>
              </div>
              <code className="text-xs text-slate-600 bg-white px-3 py-1.5 rounded-lg border border-slate-200 block font-mono">
                {service.endpoint}
              </code>
            </div>
          )}
          
          {/* Quick Action Button */}
          <button 
            onClick={handleManageClick}
            disabled={!isRunning}
            className={`w-full py-3 rounded-xl font-semibold text-sm transition-all duration-300 ${
              isRunning 
                ? `bg-gradient-to-r ${serviceInfo.gradient} text-white shadow-lg hover:shadow-xl transform hover:scale-105` 
                : 'bg-slate-200 text-slate-400 cursor-not-allowed'
            }`}>
            {isRunning ? 'Manage Service' : 'Service Offline'}
          </button>
        </div>
      </div>
      
      {/* Bottom accent line */}
      <div className={`h-1 bg-gradient-to-r ${serviceInfo.gradient} ${isRunning ? 'opacity-100' : 'opacity-30'}`}></div>
    </div>
  );
}

interface ActivityItemProps {
  icon: React.ReactNode;
  message: string;
  time: string;
  type: 'success' | 'info' | 'warning';
}

function ActivityItem({ icon, message, time, type }: ActivityItemProps) {
  return (
    <div className="group relative flex items-start gap-4 p-4 hover:bg-slate-50/50 rounded-xl transition-all duration-300">
      {/* Timeline dot connector */}
      <div className="absolute left-[20px] top-[50px] w-0.5 h-full bg-gradient-to-b from-slate-200 to-transparent"></div>
      
      {/* Icon */}
      <div className="relative z-10 transform group-hover:scale-110 transition-transform duration-300">
        {icon}
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-800 mb-1">{message}</p>
        <div className="flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-xs font-medium text-slate-500">{time}</p>
        </div>
      </div>
      
      {/* Hover indicator */}
      <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>
  );
}

export default Dashboard;
