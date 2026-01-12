// Demo file showing how to use the Supabase integration
// This file demonstrates the database service layer usage

import { alertsService } from '../services/alertsService';
import { supabase } from '../lib/supabase';

// Example 1: Fetch all alerts
async function fetchAllAlerts() {
  const result = await alertsService.getAlerts();
  
  if (result.error) {
    console.error('Error fetching alerts:', result.error);
    return [];
  }
  
  return result.data || [];
}

// Example 2: Fetch active alerts only
async function fetchActiveAlerts() {
  const result = await alertsService.getActiveAlerts();
  
  if (result.error) {
    console.error('Error fetching active alerts:', result.error);
    return [];
  }
  
  return result.data || [];
}

// Example 3: Fetch alerts with date filter
async function fetchAlertsInDateRange(startDate: Date, endDate: Date) {
  const result = await alertsService.getAlerts({
    startDate,
    endDate,
  });
  
  if (result.error) {
    console.error('Error fetching filtered alerts:', result.error);
    return [];
  }
  
  return result.data || [];
}

// Example 4: Test Supabase connection
async function testConnection() {
  try {
    const { data, error } = await supabase
      .from('alerts')
      .select('count(*)', { count: 'exact', head: true });
    
    if (error) {
      console.error('Connection test failed:', error);
      return false;
    }
    
    console.log('Connection successful. Total alerts:', data);
    return true;
  } catch (error) {
    console.error('Connection test error:', error);
    return false;
  }
}

// Usage in React component:
/*
import { useAlerts } from './hooks/useAlerts';

function MyComponent() {
  // Fetch all alerts automatically
  const { alerts, loading, error, refetch } = useAlerts();
  
  // Or fetch active alerts only
  const { alerts: activeAlerts } = useAlerts({ activeOnly: true });
  
  // Or fetch with filters
  const { alerts: filteredAlerts } = useAlerts({
    filters: {
      startDate: new Date('2024-01-01'),
      endDate: new Date('2024-12-31'),
      severity: 'Severe'
    }
  });
  
  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  
  return (
    <div>
      {alerts.map(alert => (
        <div key={alert.id}>
          <h3>{alert.event}</h3>
          <p>{alert.description}</p>
          <span>Severity: {alert.severity}</span>
        </div>
      ))}
    </div>
  );
}
*/

export {
  fetchAllAlerts,
  fetchActiveAlerts,
  fetchAlertsInDateRange,
  testConnection,
};